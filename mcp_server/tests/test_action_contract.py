from __future__ import annotations

import asyncio
import unittest

from jsonschema import ValidationError, validate

from sts2_mcp.server import create_server


class ActionContractTests(unittest.TestCase):
    def test_card_choices_require_option_index_before_execution(self) -> None:
        class Client:
            def get_available_actions(self) -> list[dict]:
                return [
                    {"name": "choose_reward_card", "requires_index": True},
                    {"name": "select_deck_card", "requires_index": True},
                    {"name": "play_card", "requires_index": True},
                ]

        server = create_server(client=Client())
        actions = asyncio.run(server.get_tool("get_available_actions")).fn()
        act_schema = asyncio.run(server.get_tool("act")).parameters
        reward, selection, play = [action["input_schema"] for action in actions]

        validate({"option_index": 0}, reward)
        validate({"option_index": 11, "card_index": None}, selection)
        validate({"card_index": 0, "target_index": 1}, play)
        validate({"action": "select_deck_card", "option_index": 11}, act_schema)
        with self.assertRaises(ValidationError):
            validate({"card_index": 0}, reward)
        with self.assertRaises(ValidationError):
            validate({"card_index": 11}, selection)
        with self.assertRaises(ValidationError):
            validate({"option_index": 0, "card_index": 0}, reward)
        with self.assertRaises(ValidationError):
            validate({"option_index": 0}, play)


if __name__ == "__main__":
    unittest.main()
