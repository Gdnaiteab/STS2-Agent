from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch
from urllib.error import URLError

from jsonschema import ValidationError, validate

from sts2_mcp.server import create_server
from sts2_mcp.client import Sts2ApiError, Sts2Client


class ActionContractTests(unittest.TestCase):
    def test_card_choices_require_option_index_before_execution(self) -> None:
        class Client:
            def get_state(self) -> dict:
                return {"combat": {"hand": [
                    {"index": 0, "requires_target": True, "valid_target_indices": [1]},
                    {"index": 1, "requires_target": False},
                ]}}

            def execute_action(self, action: str, **kwargs) -> dict:
                raise Sts2ApiError(409, "invalid_target", "This card requires target_index.")

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
        validate({"card_index": 1, "target_index": None}, play)
        validate({"action": "select_deck_card", "option_index": 11}, act_schema)
        with self.assertRaises(ValidationError):
            validate({"card_index": 0}, reward)
        with self.assertRaises(ValidationError):
            validate({"card_index": 11}, selection)
        with self.assertRaises(ValidationError):
            validate({"option_index": 0, "card_index": 0}, reward)
        with self.assertRaises(ValidationError):
            validate({"option_index": 0}, play)
        with self.assertRaises(ValidationError):
            validate({"card_index": 0, "target_index": None}, play)
        with self.assertRaises(ValidationError):
            validate({"card_index": 0, "target_index": 9}, play)

        async def rejected_action():
            from fastmcp import Client as McpClient
            async with McpClient(server) as client:
                return await client.call_tool("act", {"action": "play_card", "card_index": 0})

        outcome = asyncio.run(rejected_action()).structured_content
        self.assertFalse(outcome["accepted"])
        self.assertEqual(outcome["execution_status"], "not_executed")
        self.assertEqual(outcome["recovery"], "correct_action")
        self.assertEqual(outcome["error_code"], "invalid_target")

    def test_uncertain_action_is_not_replayed_or_marked_correctable(self) -> None:
        client = Sts2Client(max_retries=2)
        act = asyncio.run(create_server(client=client).get_tool("act")).fn
        with patch("sts2_mcp.client.request.urlopen", side_effect=URLError("response lost")) as send:
            with self.assertRaises(Sts2ApiError):
                act("play_card", card_index=0, target_index=1)
            self.assertEqual(send.call_count, 1)
        with patch("sts2_mcp.client.request.urlopen", side_effect=URLError("unavailable")) as read:
            with patch("sts2_mcp.client.time.sleep"):
                with self.assertRaises(Sts2ApiError):
                    client.get_state()
            self.assertEqual(read.call_count, 3)


if __name__ == "__main__":
    unittest.main()
