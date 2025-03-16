import cv2
import numpy as np
import asyncio
import websockets
import json
import HandTrackingModule as htm
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CollaborativePainter:
    def __init__(self):
        self.init_camera()
        self.init_drawing_settings()
        self.init_header_images()
        self.init_network()
        self.detector = htm.handDetector(detectionCon=0.85)
        self.local_mode = False  # Initialize local mode flag

    def init_camera(self):
        """Initialize the camera with specified resolution."""
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception("Could not open video capture")
            self.cap.set(3, 1280)  # Width
            self.cap.set(4, 720)   # Height
        except Exception as e:
            logger.error(f"Camera initialization error: {e}")
            raise

    def init_drawing_settings(self):
        """Set up drawing canvas and initial settings."""
        self.drawColor = (189, 189, 103)  # Default pink
        self.brushThickness = 15
        self.eraserThickness = 50
        self.imgCanvas = np.zeros((720, 1280, 3), np.uint8)
        self.displayBuffer = self.imgCanvas.copy()
        self.drawLock = asyncio.Lock()
        self.xp, self.yp = 0, 0  # Previous points
        self.drawing_buffer = []
        self.is_drawing = False

    def init_header_images(self):
        """Load and resize header images for brush selection."""
        try:
            self.header_pink = cv2.imread("Header/1.png", cv2.IMREAD_UNCHANGED)
            self.header_blue = cv2.imread("Header/2.png", cv2.IMREAD_UNCHANGED)
            self.header_green = cv2.imread("Header/3.png", cv2.IMREAD_UNCHANGED)
            self.header_eraser = cv2.imread("Header/4.png", cv2.IMREAD_UNCHANGED)
            
            # Resize headers to 1280x125
            self.header_pink = cv2.resize(self.header_pink, (1280, 125))
            self.header_blue = cv2.resize(self.header_blue, (1280, 125))
            self.header_green = cv2.resize(self.header_green, (1280, 125))
            self.header_eraser = cv2.resize(self.header_eraser, (1280, 125))
            
            self.current_brush = 'pink'
            self.current_header = self.header_pink
            
        except Exception as e:
            logger.error(f"Error loading header images: {e}")
            raise

    def init_network(self):
        """Initialize network-related variables."""
        self.ws = None
        self.running = True
        self.connected = False
        self.retry_count = 0
        self.max_retries = 3

    def update_current_brush(self, x1):
        """Update brush color and header based on x-coordinate."""
        if 250 < x1 < 450:
            self.drawColor = (189, 189, 103)  # Pink
            self.current_brush = 'pink'
            self.current_header = self.header_pink
        elif 550 < x1 < 750:
            self.drawColor = (86, 48, 189)    # Blue
            self.current_brush = 'blue'
            self.current_header = self.header_blue
        elif 800 < x1 < 1000:
            self.drawColor = (17, 141, 255)   # Green
            self.current_brush = 'green'
            self.current_header = self.header_green
        elif 1050 < x1 < 1200:
            self.drawColor = (0, 0, 0)        # Black (eraser)
            self.current_brush = 'eraser'
            self.current_header = self.header_eraser

    async def connect_to_server(self):
        """Attempt to connect to the WebSocket server."""
        while self.retry_count < self.max_retries:
            try:
                self.ws = await websockets.connect(
                    'ws://13.83.85.29:8080',
                    ping_interval=None,
                    max_size=None
                )
                self.connected = True
                logger.info("Connected to server")
                return True
            except Exception as e:
                logger.error(f"Connection attempt {self.retry_count + 1} failed: {e}")
                self.retry_count += 1
                await asyncio.sleep(1)
        logger.error("Max retries reached. Server connection failed.")
        return False

    async def send_drawing(self, x1, y1, x2, y2, color, thickness):
        """Draw locally and send to server if connected and not in local mode."""
        async with self.drawLock:
            cv2.line(self.imgCanvas, (x1, y1), (x2, y2), color, thickness)
            self.displayBuffer = self.imgCanvas.copy()
        
        if not self.local_mode and self.ws and self.connected:
            try:
                data = {
                    'type': 'draw',
                    'x1': int(x1),
                    'y1': int(y1),
                    'x2': int(x2),
                    'y2': int(y2),
                    'color': list(color),
                    'thickness': int(thickness),
                    'timestamp': str(datetime.now().timestamp())
                }
                asyncio.create_task(self.ws.send(json.dumps(data)))
            except Exception as e:
                logger.error(f"Error sending drawing: {e}")
                self.connected = False

    async def receive_drawings(self):
        """Receive drawing data from the server (runs only if connected)."""
        while self.running:
            if self.ws and self.connected:
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=0.01)
                    data = json.loads(message)
                    if data.get('type') == 'draw':
                        async with self.drawLock:
                            cv2.line(
                                self.imgCanvas,
                                (data['x1'], data['y1']),
                                (data['x2'], data['y2']),
                                tuple(data['color']),
                                data['thickness']
                            )
                            self.displayBuffer = self.imgCanvas.copy()
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.error("Connection closed")
                    self.connected = False
                    await self.connect_to_server()
                except Exception as e:
                    logger.error(f"Error receiving drawing: {e}")
                await asyncio.sleep(0.001)

    def overlay_header(self, img):
        """Overlay the header image with alpha blending."""
        if self.current_header.shape[2] == 4:  # Check for alpha channel
            alpha = self.current_header[:, :, 3] / 255.0
            bgr = self.current_header[:, :, :3]
            for c in range(3):
                img[0:125, 0:1280, c] = (
                    img[0:125, 0:1280, c] * (1 - alpha) +
                    bgr[:, :, c] * alpha
                )

    async def run(self):
        """Main loop to process video and handle drawing."""
        # Determine mode based on server connection
        self.local_mode = not await self.connect_to_server()
        if self.local_mode:
            logger.info("Running in local mode")
        
        # Start receiving task only if not in local mode
        receive_task = None
        if not self.local_mode:
            receive_task = asyncio.create_task(self.receive_drawings())

        try:
            while True:
                success, img = self.cap.read()
                if not success:
                    continue

                img = cv2.flip(img, 1)  # Mirror the image
                img = self.detector.findHands(img)
                lmList, bbox = self.detector.findPosition(img, draw=False)

                if len(lmList) != 0:
                    x1, y1 = lmList[8][1:]  # Index finger tip
                    x2, y2 = lmList[12][1:] # Middle finger tip
                    fingers = self.detector.fingersUp()

                    # Selection mode (index and middle fingers up)
                    if fingers[1] and fingers[2]:
                        self.is_drawing = False
                        self.xp, self.yp = 0, 0
                        if y1 < 125:
                            self.update_current_brush(x1)
                        cv2.circle(img, (x1, y1), 15, self.drawColor, cv2.FILLED)

                    # Drawing mode (index finger up, middle finger down)
                    elif fingers[1] and not fingers[2]:
                        if not self.is_drawing:
                            self.xp, self.yp = x1, y1
                            self.is_drawing = True
                        cv2.circle(img, (x1, y1), 15, self.drawColor, cv2.FILLED)
                        thickness = self.eraserThickness if self.current_brush == 'eraser' else self.brushThickness
                        await self.send_drawing(self.xp, self.yp, x1, y1, self.drawColor, thickness)
                        self.xp, self.yp = x1, y1
                    else:
                        self.is_drawing = False

                # Overlay canvas onto the video feed
                imgGray = cv2.cvtColor(self.displayBuffer, cv2.COLOR_BGR2GRAY)
                _, imgInv = cv2.threshold(imgGray, 50, 255, cv2.THRESH_BINARY_INV)
                imgInv = cv2.cvtColor(imgInv, cv2.COLOR_GRAY2BGR)
                img = cv2.bitwise_and(img, imgInv)
                img = cv2.bitwise_or(img, self.displayBuffer)

                self.overlay_header(img)

                cv2.imshow("Collaborative Drawing", img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

                await asyncio.sleep(0.001)

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            await self.cleanup(receive_task)

    async def cleanup(self, receive_task):
        """Clean up resources."""
        self.running = False
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        if self.ws:
            await self.ws.close()
        if receive_task:
            try:
                await receive_task
            except Exception:
                pass

def main():
    """Entry point of the application."""
    try:
        painter = CollaborativePainter()
        asyncio.run(painter.run())
    except Exception as e:
        logger.error(f"Main error: {e}")

if __name__ == "__main__":
    main()