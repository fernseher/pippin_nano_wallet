# From Guilhermelawless:
# https://github.com/guilhermelawless/nano-dpow/blob/master/server/dpow/nano_websocket.py
from aiohttp import log
import asyncio
from websockets.exceptions import ConnectionClosed
from websockets.client import connect
import rapidjson as json
import traceback
from pippin.network.work_client import WorkClient


def subscription(topic: str, ack: bool = False, options: dict = None):
    d = {"action": "subscribe", "topic": topic, "ack": ack}
    if options is not None:
        d["options"] = options
    return d


class WebsocketClient(object):

    def __init__(self, uri, callback):
        self.uri = uri
        self.arrival_cb = callback
        self.ws = None
        self.stop = False

    async def setup(self, silent=False):
        try:
            self.ws = await connect(self.uri)
            await self.ws.send(json.dumps(subscription("confirmation", ack=True)))
            # ack, timeout after waiting for 10 seconds
            await asyncio.wait_for(self.ws.recv(), 10)
        except asyncio.TimeoutError:
            if not silent:
                log.server_logger.critical(
                    "NANO WS: No response from connected websocket server. Ensure this server allows subscription to confirmations with no set filters")
            raise
        except Exception as e:
            if not silent:
                log.server_logger.critical(
                    "NANO WS: Error connecting to websocket server. Check your settings in ~/PippinData/config.yaml")
                log.server_logger.error(traceback.format_exc())
            raise

    async def close(self):
        self.stop = True
        await self.ws.wait_closed()

    async def reconnect_forever(self):
        log.server_logger.warn(
            "NANO WS: Attempting websocket reconnection every 30 seconds...")
        while not self.stop:
            try:
                await self.setup(silent=True)
                log.server_logger.warn("NANO WS: Connected to websocket!")
                break
            except:
                log.server_logger.debug(
                    "NANO WS: Websocket reconnection failed")
                await asyncio.sleep(30)

    async def loop(self):
        while not self.stop:
            try:
                rec = json.loads(await self.ws.recv())
                topic = rec.get("topic", None)
                if topic and topic == "confirmation":
                    await self.arrival_cb(rec["message"])
            except KeyboardInterrupt:
                break
            except ConnectionClosed as e:
                log.server_logger.error(
                    f"NANO WS: Connection closed to websocket. Code: {e.code} , reason: {e.reason}.")
                await self.reconnect_forever()
            except Exception as e:
                log.server_logger.critical(
                    f"NANO WS: Unknown exception while handling getting a websocket message:\n{traceback.format_exc()}")
                await self.reconnect_forever()
