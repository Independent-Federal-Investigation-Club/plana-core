import os
from typing import Optional, AsyncGenerator, List, Optional

from loguru import logger
from plana.services.openai import OpenAI


class AgentMemory:
    def __init__(
        self,
        system_prompt: str = "",
        max_length: int = 8192,
    ):
        self.system_prompt: str = system_prompt
        self.max_tokens: int = max_length

        self.memories: dict[int, list] = {}

    def create_memory(self, context_id: int) -> list:
        """
        Create a new memory for a specific conversation.

        Args:
            context_id (int): The ID of the conversation.

        Returns:
            list: The newly created memory object.
        """

        system_prompt = {
            "role": "system",
            "content": self.system_prompt,
        }
        self.memories[context_id] = [system_prompt]
        return self.memories[context_id]

    def reset_memory(self, context_id: int):
        """
        Reset the memory for a specific conversation.

        Args:
            context_id (int): The ID of the conversation.
        """
        self.create_memory(context_id)

    def get_memory(self, context_id: int) -> List[dict]:
        """
        Get the memory for a specific conversation. If it doesn't exist, create a new one.

        Args:
            context_id (int): The ID of the conversation.

        Returns:
            list: The memory object for the conversation.
        """

        if context_id not in self.memories:
            self.create_memory(context_id)

        # format openai message to a list of dicts
        memory = [dict(m) for m in self.memories[context_id]]
        self.memories[context_id] = memory

        return self.memories[context_id]

    def set_memory(self, context_id: int, memories: List[dict]) -> None:
        """
        Set the memory for a specific conversation.

        Args:
            context_id (int): The ID of the conversation.
            memories (List[dict]): The memory object for the conversation.
        """
        self.memories[context_id] = memories

    def append_messages(self, context_id: int, messages: List[dict]) -> None:
        """
        Add a message to a specific conversation.

        Args:
            context_id (int): The ID of the conversation.
            messages (List[dict]): List of messages to append, each message containing 'role' and 'content' following openai standard.
        """
        memory = self.get_memory(context_id)
        memory.extend(messages)

        memory = self.trim_memory(memory=memory)
        self.set_memory(context_id, memory)

    def trim_memory(self, memory: List[dict]) -> List[dict]:
        """
        Trim the memories list if it exceeds the maximum allowed (in-memory). This is used to avoid having to re-initialize the memory list.
        """
        # trim the memory if it exceeds the maximum allowed tokens (approximate)
        token_count = sum((len(m.get("content", "")) * 1.2 for m in memory))
        if token_count < self.max_tokens - 1024:
            return memory

        # only keep the system prompt and remove the most oldest 2 messages
        memory = memory[:3] + memory[5:]
        return memory


class ChatRequest:
    def __init__(self, message: str, context_id: int):
        self.message = message
        self.response: Optional[str] = None
        self.context_id = context_id
        self.async_stream: AsyncGenerator[Optional[str]] = None


class PlanaAgent:
    def __init__(self, system_prompt: Optional[str] = None):
        self.max_length = 8192
        self.system_prompt = system_prompt

        api_url = os.getenv("OPENAI_API_BASE", None)
        api_key = os.getenv("OPENAI_API_KEY", None)
        model = os.getenv("OPENAI_API_MODEL", None)

        if self.system_prompt is None:
            self.system_prompt = os.getenv("DEFAULT_SYSTEM_PROMPT", None)

        if api_url is None or api_key is None or model is None or self.system_prompt is None:
            logger.error(
                "OpenAI API configuration is missing. Please check your environment variables."
            )
            raise ValueError("OpenAI API configuration is missing.")

        self.client = OpenAI(
            api_key=api_key,
            base_url=api_url,
            model=model,
        )
        self.memory = AgentMemory(system_prompt=self.system_prompt, max_length=self.max_length)

    async def query(self, request: ChatRequest) -> ChatRequest:
        """
        Send a message to the chatbot and return the response. This is a wrapper around OpenAI's send_message method.

        Args:
            request (ChatRequest): The chat request object.

        Returns:
            AsyncGenerator[str, None]: The response from the chatbot.
        """
        if self.client is None:
            return "Plana is not available at this moment..."

        user_payload = {"role": "user", "content": request.message}
        memory = self.memory.get_memory(context_id=request.context_id)

        messages = memory.copy()
        messages.extend([user_payload])
        request.async_stream = self.client.async_chat_stream(messages=messages)

        return request

    def append_memory(self, context_id: int, user_message: str, assistant_message: str) -> None:
        """
        Append the user and assistant messages to the memory.

        Args:
            context_id (int): The ID of the conversation.
            user_message (str): The user message.
            assistant_message (str): The assistant message.
        """

        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ]

        self.memory.append_messages(context_id=context_id, messages=messages)

    def reset_memory(self, context_id: int) -> None:
        """Reset the memory for a specific conversation."""
        self.memory.reset_memory(context_id=context_id)
