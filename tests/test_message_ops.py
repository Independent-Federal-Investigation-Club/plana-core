import asyncio

from dotenv import load_dotenv

from plana.models.message import (
    Button,
    Embed,
    EmbedField,
    EmbedFooter,
    Emoji,
    Message,
    SelectMenu,
    SelectOption,
)
from plana.models.react_role import ReactRoleSetting, RoleAssignment


async def test_create_react_role(guild_id: int, message_id: int):

    react_role_data = ReactRoleSetting(
        guild_id=guild_id,
        message_id=message_id,
        name="React Role Example",
        role_assignments=[
            RoleAssignment(
                role_ids=[1396301221366599781],
                trigger_id="join_now",
            ),
            RoleAssignment(
                role_ids=[1396301254161993748],
                trigger_id="support",
            ),
            RoleAssignment(
                role_ids=[1396301274185469953],
                trigger_id="options_menu-option_1",
            ),
            RoleAssignment(
                role_ids=[1396301848935141397],
                trigger_id="options_menu-option_2",
            ),
            RoleAssignment(
                role_ids=[1396301312752353301],
                trigger_id="options_menu-option_3",
            ),
            RoleAssignment(
                role_ids=[1396299720174862437],
                trigger_id="👍",
            ),
            RoleAssignment(
                role_ids=[1396301728717996083],
                trigger_id="👎",
            ),
        ],
        enabled=True,
    )

    try:
        react_role = await ReactRoleSetting.create(
            guild_id=guild_id, data=react_role_data.model_dump(mode="json", exclude_unset=True)
        )
        print(f"React role created successfully: {react_role}")
    except Exception as e:
        print(f"Error creating react role: {e}")


async def test_create_message(guild_id: int, channel_id: int) -> Message:
    embed = Embed(
        title="Welcome to the Server",
        description="This is a custom welcome message.",
        color=0x00FF00,
        footer=EmbedFooter(text="Powered by Klee"),
        image="https://media.discordapp.net/attachments/471701478382370818/1322771375563214889/image.png?ex=68791997&is=6877c817&hm=1084f74d7a0bdb819649cfb4444335c6bcb07fc84840de86e8f440f7e91c6a8a&",
        fields=[
            EmbedField(name="Rules", value="Please read the rules.", inline=False),
            EmbedField(name="Announcements", value="Check announcements regularly.", inline=True),
        ],
    )

    components = [
        Button(
            style=1,
            label="Join Now",
            custom_id="join_now",
            emoji=Emoji(name="👋"),
        ),
        Button(
            style=5,
            label="Learn More",
            url="https://example.com",
        ),
        Button(
            style=3,
            label="Support",
            custom_id="support",
            emoji=Emoji(name="Fire", id=1212963251277668382, animated=False),
        ),
        SelectMenu(
            custom_id="options_menu",
            placeholder="Choose an option",
            options=[
                SelectOption(label="Option 1", value="option_1"),
                SelectOption(label="Option 2", value="option_2"),
                SelectOption(label="Option 3", value="option_3"),
            ],
        ),
    ]

    message = Message(
        content="Hello, new member!",
        embeds=[embed],
        components=components,
        guild_id=guild_id,
        channel_id=channel_id,
        published=True,
        reactions=[Emoji(name="👍"), Emoji(name="👎")],
    )

    try:
        return await Message.create(
            guild_id=message.guild_id, data=message.model_dump(mode="json", exclude_unset=True)
        )

    except Exception as e:
        print(f"Error creating message: {e}")
        return


async def test_update_message(guild_id: int, message_id: int):
    try:
        message: Message = await Message.get(
            guild_id=guild_id,
            id=message_id,
        )

        if not message:
            print("Message not found.")
            return

        if message.content:
            message.content = "This is an updated message content."

        if message.embeds:
            message.embeds[0].title = "Updated Title"
            message.embeds[0].description = "Updated description."

        updated_message = await Message.update(
            guild_id=message.guild_id,
            id=message.message_id,
            data=message.model_dump(mode="json", exclude_unset=True),
        )

        print(f"Message updated successfully: {updated_message}")

    except Exception as e:
        print(f"Error updating message: {e}")


async def test_delete_message(guild_id: int, message_id: int):
    try:
        await Message.delete(
            guild_id=guild_id,
            id=message_id,
        )
        print("Message deleted successfully.")
    except Exception as e:
        print(f"Error deleting message: {e}")


async def main():
    load_dotenv()
    # Example usage of the Message model
    # message = await test_create_message(
    #     guild_id=1210097999699779594, channel_id=1331836334632861696
    # )
    await test_create_react_role(guild_id=1210097999699779594, message_id=1396299145605550202)

    # print(message.model_dump_json(exclude_unset=True, indent=2))
    # await test_update_message(guild_id=1210097999699779594, message_id=1395970526605742174)


if __name__ == "__main__":
    asyncio.run(main())
