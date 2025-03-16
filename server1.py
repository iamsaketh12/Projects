import asyncio
import websockets
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DrawingServer:
    def __init__(self, forward_server_url=None):
        self.connected_clients = set()
        self.forward_server_url = forward_server_url
        self.drawing_history = []

    async def store_and_broadcast(self, message, sender=None):
        try:
            data = json.loads(message)
            self.drawing_history.append(data)

            # Forward the drawing to all other connected clients
            for client in list(self.connected_clients):
                if client != sender:
                    try:
                        await client.send(message)
                    except websockets.exceptions.ConnectionClosed:
                        self.connected_clients.remove(client)

            # Forward the drawing to the secondary server if configured
            if self.forward_server_url:
                try:
                    async with websockets.connect(self.forward_server_url) as forward_socket:
                        await forward_socket.send(message)
                except Exception as e:
                    logger.error(f"Failed to forward to secondary server: {e}")

        except Exception as e:
            logger.error(f"Error in store_and_broadcast: {e}")

    async def send_drawing_history(self, websocket):
        try:
            for drawing in self.drawing_history:
                await websocket.send(json.dumps(drawing))
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected during history send")
        except Exception as e:
            logger.error(f"Error sending drawing history: {e}")

    async def handle_client(self, websocket):
        self.connected_clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.connected_clients)}")

        # Send drawing history to the new client
        await self.send_drawing_history(websocket)

        try:
            async for message in websocket:
                await self.store_and_broadcast(message, sender=websocket)
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")
        finally:
            self.connected_clients.remove(websocket)
            logger.info(f"Client removed. Total clients: {len(self.connected_clients)}")

    async def start_server(self):
        try:
            server = await websockets.serve(self.handle_client, "0.0.0.0", 8080)
            logger.info("Server started on ws://0.0.0.0:8080")
            await server.wait_closed()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            for client in self.connected_clients:
                await client.close()
            self.connected_clients.clear()

def main():
    forward_server_url = "ws://secondary-server:8081"  # Replace with actual secondary server URL
    server = DrawingServer(forward_server_url)

    try:
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown by user")
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    main()
