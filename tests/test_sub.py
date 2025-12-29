import asyncio
from plana.models.message import Message
from plana.services.sub import RedisEventSubscriber, PlanaEvents, EventPayload


async def handle_message_create(event_data: EventPayload):
    """Handle MESSAGE_CREATE events."""
    if event_data.data:
        # Convert to Message BaseModel if needed
        message = event_data.data
        if isinstance(message, dict):
            message = Message.model_validate(message)

        print(f"New message created:")
        print(f"  ID: {message.id}")
        print(f"  Content: {message.content}")
        print(f"  Guild ID: {event_data.guild_id}")
        print(f"  Timestamp: {event_data.timestamp}")
        print("-" * 50)

        print(message.model_dump_json(indent=4))


async def handle_message_delete(event_data: EventPayload):
    """Handle MESSAGE_DELETE events."""
    print(f"Message deleted:")
    print(f"  Message ID: {event_data.message_id}")
    print(f"  Guild ID: {event_data.guild_id}")
    print(f"  Timestamp: {event_data.timestamp}")
    print("-" * 50)


async def main():
    # Initialize Redis subscriber
    subscriber = RedisEventSubscriber(redis_url="redis://localhost:6379")

    # Register event handlers
    subscriber.register_handler(PlanaEvents.MESSAGE_CREATE, handle_message_create)
    subscriber.register_handler(PlanaEvents.MESSAGE_DELETE, handle_message_delete)

    # Use async context manager for proper cleanup
    async with subscriber:
        # Option 1: Subscribe to specific guilds
        # await subscriber.subscribe_to_guilds(guild_ids=[1, 2, 3])

        # Option 2: Subscribe to all guilds
        await subscriber.subscribe_to_guilds()

        # Start listening for messages
        print("Starting to listen for message events...")
        print("Press Ctrl+C to stop")

        try:
            await subscriber.start_listening()
        except KeyboardInterrupt:
            print("\nStopping subscriber...")


if __name__ == "__main__":
    asyncio.run(main())
