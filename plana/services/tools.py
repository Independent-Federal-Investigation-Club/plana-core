"""
Discord AI tools for bot interactions.

This module provides various tools that the AI agent can use to interact
with Discord features and provide useful information to users.
"""

import re
import random
import docstring_parser

from typing import List, get_type_hints
from inspect import signature, getdoc


def get_function_specs(func):
    """
    Convert a function's signature, type hints and docstring into OpenAI function specification
    """
    sig = signature(func)
    doc = docstring_parser.parse(getdoc(func))
    type_hints = get_type_hints(func)

    # Type conversion mapping
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        List: "array",
        # Add more type mappings as needed
    }

    # Create parameters schema
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        param_type = type_hints.get(param_name, str)

        # Convert Python type to OpenAI type
        openai_type = type_map.get(param_type, "string")  # default to string if type not found

        # Handle special cases like List[str], List[int], etc.
        if hasattr(param_type, "__origin__") and param_type.__origin__ is list:
            openai_type = "array"
            item_type = param_type.__args__[0]
            properties[param_name] = {
                "type": openai_type,
                "items": {"type": type_map.get(item_type, "string")},
                "description": next(
                    (p.description for p in doc.params if p.arg_name == param_name), ""
                ),
            }
        else:
            properties[param_name] = {
                "type": openai_type,
                "description": next(
                    (p.description for p in doc.params if p.arg_name == param_name), ""
                ),
            }

        # If parameter has no default value, it's required
        if param.default == param.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc.short_description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            "strict": False,
        },
    }


async def dice_roll(dice_notation: str) -> str:
    """Roll dice using standard D&D notation NdX[±M] (e.g., '2d6', '1d20+2'), used for decision-making or randomization.

    Args:
        dice_notation: Dice notation string (e.g., '2d6', '1d20+2')

    Returns:
        String containing roll results
    """
    pattern = r"^(\d+)d(\d+)([+-]\d+)?$"
    match = re.match(pattern, dice_notation.lower().replace(" ", ""))

    if not match:
        return "❌ Invalid dice notation. Use format: NdX[±M] (e.g., '2d6', '1d20+2')"

    num_dice = int(match.group(1))
    dice_sides = int(match.group(2))
    modifier = int(match.group(3) or 0)

    if num_dice > 10:
        return "❌ Too many dice to roll, limit is 10"

    if dice_sides > 100:
        return "❌ Dice sides too large, limit is 100"

    rolls = [random.randint(1, dice_sides) for _ in range(num_dice)]
    total = sum(rolls) + modifier

    result = f"🎲 Rolling {dice_notation}: {rolls}"
    if modifier:
        result += f" (modifier: {modifier:+})"
    result += f" = **{total}**"

    return result


async def flip_coin() -> str:
    """Flip a coin to make a random decision.

    Returns:
        Result of the coin flip (Heads or Tails)
    """
    result = random.choice(["Heads", "Tails"])
    emoji = "🌕" if result == "Heads" else "🌑"
    return f"{emoji} **{result}**!"


# Map of available tools for the AI agent
AVAIBLE_TOOLS = {
    "dice_roll": dice_roll,
    "flip_coin": flip_coin,
}


def get_avaiable_tools():
    return [get_function_specs(func) for func in AVAIBLE_TOOLS.values()]
