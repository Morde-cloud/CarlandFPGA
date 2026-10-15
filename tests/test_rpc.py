import asyncio
import json
import sys
import unittest

from fpga_mesh.rpc import (InMemoryTransport, JsonRpcError, JsonRpcSession,
                           RequestNotSentError, StdioTransport)


class JsonRpcSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_matches_response_even_when_replies_arrive_out_of_order(self):
        transport = InMemoryTransport()
        session = JsonRpcSession(transport)
        first = asyncio.create_task(session.request("model/list", {"limit": 1}))
        second = asyncio.create_task(session.request("account/read", {}))
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        first_id = json.loads(await transport.next_client_message())["id"]
        second_id = json.loads(await transport.next_client_message())["id"]
        await transport.inject_server_message(
            json.dumps({"jsonrpc": "2.0", "id": second_id, "result": {"ok": 2}})
        )
        await transport.inject_server_message(
            json.dumps({"jsonrpc": "2.0", "id": first_id, "result": {"ok": 1}})
        )

        self.assertEqual(await first, {"ok": 1})
        self.assertEqual(await second, {"ok": 2})

    async def test_notifications_are_queued_without_blocking_requests(self):
        transport = InMemoryTransport()
        session = JsonRpcSession(transport)
        await transport.inject_server_message(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "account/rateLimits/updated",
                    "params": {"usedPercent": 10},
                }
            )
        )
        await asyncio.sleep(0)

        notification = await session.next_notification()
        self.assertEqual(notification.method, "account/rateLimits/updated")
        self.assertEqual(notification.params["usedPercent"], 10)

    async def test_server_error_raises_with_method_context(self):
        transport = InMemoryTransport()
        session = JsonRpcSession(transport)
        pending = asyncio.create_task(session.request("thread/start", {}))
        await asyncio.sleep(0)
        request = json.loads(await transport.next_client_message())
        await transport.inject_server_message(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "error": {"code": -32602, "message": "invalid params"},
                }
            )
        )
        with self.assertRaises(JsonRpcError):
            await pending

    async def test_eof_fails_pending_request_instead_of_hanging(self):
        transport = InMemoryTransport()
        session = JsonRpcSession(transport)
        pending = asyncio.create_task(session.request("thread/start", {}))
        await asyncio.sleep(0)
        await transport.next_client_message()
        await transport.inject_server_message("")
        with self.assertRaises(ConnectionError):
            await asyncio.wait_for(pending, 1)
        await session.close()

    async def test_request_after_eof_is_not_sent_and_is_distinguishable(self):
        transport = InMemoryTransport()
        session = JsonRpcSession(transport)
        await transport.inject_server_message("")
        await session._reader
        self.assertFalse(session.is_alive)
        with self.assertRaises(RequestNotSentError):
            await session.request("turn/start", {})
        self.assertTrue(transport._client_writes.empty())
        self.assertFalse(session._pending)
        await session.close()

    async def test_partial_send_error_is_not_mislabeled_safe_to_retry(self):
        class PartialWrite(InMemoryTransport):
            async def send(self, payload):
                await super().send(payload)
                raise ConnectionError("reply may be lost after write")
        session = JsonRpcSession(PartialWrite())
        try:
            with self.assertRaises(ConnectionError) as error:
                await session.request("turn/start", {})
            self.assertNotIsInstance(error.exception, RequestNotSentError)
            self.assertFalse(session._pending)
        finally:
            await session.close()

    async def test_unknown_server_request_has_explicit_error_reply(self):
        transport = InMemoryTransport()
        session = JsonRpcSession(transport)
        try:
            await session.reject(7, message="No interactive approval handler")
            reply = json.loads(await transport.next_client_message())
            self.assertEqual(reply["id"], 7)
            self.assertEqual(reply["error"]["code"], -32601)
            self.assertNotIn("result", reply)
        finally:
            await session.close()

    async def test_server_dynamic_tool_request_can_be_answered(self):
        transport = InMemoryTransport()
        session = JsonRpcSession(transport)
        await transport.inject_server_message(json.dumps({
            "jsonrpc": "2.0", "id": 51, "method": "item/tool/call",
            "params": {"tool": "child_status", "arguments": {}},
        }))
        request = await asyncio.wait_for(session.next_notification(), 1)
        self.assertEqual(request.request_id, 51)
        await session.respond(51, {"contentItems": [
            {"type": "inputText", "text": "ok"},
        ], "success": True})
        reply = json.loads(await transport.next_client_message())
        self.assertEqual(reply["id"], 51)
        self.assertTrue(reply["result"]["success"])
        await session.close()

    async def test_unmatched_string_response_id_does_not_kill_reader(self):
        transport = InMemoryTransport()
        session = JsonRpcSession(transport)
        pending = asyncio.create_task(session.request("thread/start", {}))
        request = json.loads(await transport.next_client_message())
        await transport.inject_server_message(json.dumps({
            "jsonrpc": "2.0", "id": "not-our-id", "result": {},
        }))
        await transport.inject_server_message(json.dumps({
            "jsonrpc": "2.0", "id": request["id"], "result": {"ok": True},
        }))
        self.assertEqual(await asyncio.wait_for(pending, 1), {"ok": True})
        await session.close()

    async def test_stdio_transport_drains_large_stderr_without_hanging_stdout(self):
        command = [sys.executable, "-c", (
            "import sys; sys.stderr.write('x' * 8000000); "
            "sys.stderr.flush(); sys.stdout.write('READY\\n'); sys.stdout.flush()"
        )]
        transport = StdioTransport(command)
        await transport.start()
        try:
            self.assertEqual(await asyncio.wait_for(transport.recv(), 2), "READY")
        finally:
            await transport.close()


if __name__ == "__main__":
    unittest.main()
