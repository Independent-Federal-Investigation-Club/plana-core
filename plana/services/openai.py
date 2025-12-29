import json
import random
from asyncio import iscoroutinefunction
from typing import AsyncGenerator, List

from loguru import logger
from openai import AsyncOpenAI

from plana.services.tools import AVAIBLE_TOOLS, get_avaiable_tools
from plana.utils.helper import dump_json, format_traceback


class OpenAI:
    def __init__(
        self,
        base_url="https://api.openai.com/v1",
        api_key=None,
        model="gpt-4o-mini",
        max_tokens=2048,
    ):
        """
        Initialize ClaudeAPI with cookie. This is called by __init__ and should not be called directly

        Args:
                cookie: Cookie to use for
        """
        self.max_tokens = max_tokens
        self.model = model

        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=3, timeout=100)

    async def handle_tool_call(self, tool_name: str, tool_args_str: str):
        """
        Handle tool calls from the model and return the tool response.

        Args:
            tool_name (str): The name of the tool to call.
            tool_args_str (str): The arguments to pass to the tool
        Returns:
            dict: The tool response.
        """

        tool_args = json.loads(tool_args_str)
        tool_to_invoke = AVAIBLE_TOOLS[tool_name]

        # if tool is async function, await it
        if iscoroutinefunction(tool_to_invoke):
            tool_response = await tool_to_invoke(**tool_args)
        else:
            tool_response = tool_to_invoke(**tool_args)

        return tool_response

    async def async_chat_stream(
        self, messages: List[dict], timeout: int = 120
    ) -> AsyncGenerator[str, None]:
        """
        Stream the assistant's response while watching for tool usage in a loop
        until there are no more tool calls.

        Args:
            messages (List[dict]): A list of messages in the conversation.
            timeout (int): Timeout value for the request.

        Returns:
            AsyncGenerator[str, None]:
                An async generator that yields content chunks of the final answer.
        """

        logger.info(f"Starting chat stream with messages: {messages[-1]['content']}")
        dump_json(messages, "messages.json")

        try:
            # generate random temperature. and penality, round to .2f
            temp = round(random.uniform(0.7, 1), 2)
            top_p = round(random.uniform(0.9, 0.95), 2)
            pres_pen = round(random.uniform(1, 1.3), 2)

            while True:
                # Step 1: Make the streaming request
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=get_avaiable_tools(),
                    tool_choice="auto",
                    stream=True,
                    timeout=timeout,
                    temperature=temp,
                    top_p=top_p,
                    max_tokens=self.max_tokens,
                    presence_penalty=pres_pen,
                )

                # Store recovered tool calls in each pass
                current_tool_calls = {}
                found_tool_call = False

                # Iterate over the streaming chunks
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason

                    # Yield any partial content if it has any
                    if delta.content:
                        yield delta.content

                    # Check for tool calls, and parse them
                    if delta.tool_calls:
                        found_tool_call = True
                        for tool_call in delta.tool_calls:
                            index = tool_call.index
                            if index not in current_tool_calls:
                                current_tool_calls[index] = tool_call
                            else:
                                current_tool_calls[
                                    index
                                ].function.arguments += tool_call.function.arguments

                    elif finish_reason is not None:
                        print(finish_reason)
                        break

                if current_tool_calls:
                    logger.info(f"Current tool calls: {current_tool_calls}")

                # If no tool calls found, we can break the loop
                if not found_tool_call:
                    break

                # Otherwise, handle the tool calls
                tool_call_payload = []
                for tool_call in current_tool_calls.values():
                    tool_call_payload.append(
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                            "index": tool_call.index,
                        }
                    )

                # Append the tool calls to the messages
                messages.append({"role": "assistant", "tool_calls": tool_call_payload})

                # Execute each tool call and append its response
                for tool_call in current_tool_calls.values():
                    print(tool_call.function.name)
                    tool_response = await self.handle_tool_call(
                        tool_call.function.name, tool_call.function.arguments
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_response, ensure_ascii=False),
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to send request: Errors: {format_traceback(e, advance=True)}")
            yield "Plana is not available at this moment..."
