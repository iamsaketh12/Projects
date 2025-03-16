Virtual Painter
Virtual Painter is a collaborative drawing application that allows users to draw simultaneously on multiple computers, with changes automatically syncing across all connected devices.
Setup
Prerequisites
Python 3.x installed on all computers
Network connectivity between the computers
Installation
Clone the repository or download the project files to all computers that will participate in the collaborative drawing session.
Install the required dependencies:
bash
pip install -r requirements.txt
Usage
Step 1: Connect to the Server
On the computer designated as the server, run the server script:
bash
python server.py
Note the IP address and port number displayed by the server script.
Step 2: Run VirtualPainter.py
On each computer (including the server computer), open a terminal or command prompt and navigate to the project directory.
Run the VirtualPainter.py script:
bash
python VirtualPainter.py
When prompted, enter the server's IP address and port number.
Step 3: Start Drawing
Once all computers are connected, you can start drawing on any of the connected devices.
Your drawings will automatically update and appear on all other connected computers in real-time.
Features
Real-time collaborative drawing
Automatic synchronization across multiple devices
Customizable brush colors and sizes (if implemented)