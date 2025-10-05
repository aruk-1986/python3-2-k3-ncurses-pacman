🟡 Python ncurses Pac-Man (Python 3.8+ and 2.7+ and Kindle 3 Keyboard)

A terminal-based Pac-Man clone written in Python using the ncurses library.
Play Pac-Man right in your terminal — no graphics, just characters and imagination!

🎮 Features

* Classic Pac-Man gameplay in text mode
* Customisable maze loaded from pacman-map.txt
* Power pills and fruit bonuses (depending on your map design)
* Simple ghost AI that chases Pac-Man
* Clean, minimal code for learning and modification
* Adapted to run on Python 3.8+ and 2.7 and Kindle 3 Keyboard

🕹️ Controls

| Key | Action |
|-----|---------|
| `Arrow keys` | Move Pac-Man |
| `Space` | Next level |
| `r` | Restart game |
| `q` | Quit game |

📦 Requirements

* Python 3.8+ or 2.7+
* ncurses (already available on Linux / macOS)

On ***Windows***, install windows-curses:
```bash
pip install windows-curses
```

▶️ Running the Game

Clone the repository and run the main file:

```bash
git clone https://github.com/aruk-1986/python3-2-k3-ncurses-pacman.git
cd python3-2-k3-ncurses-pacman
python3 pacman_k3.py
```

Make sure pacman-map.txt is in the same folder — it defines the maze layout.
You can edit it to design your own mazes!

🗺️ Custom Maps

pacman-map.txt is a simple text file where each character represents part of the maze, as follows:

* "#" = Wall
* "-" = Dead space
* "." = Pellet
* "o" = Power Pill
* "*" = Fruit
* "n" = Ghost
* "c" = Pacman
* "<" = Warp Tunnel
* ">" = Warp Tunnel

Try changing walls (#) and dots (.) to make your own challenges. If you add new symbols for special items, update the parsing logic in pacman.py accordingly.

📸 Screenshots

![Pac-Man Screenshot](images/screenshot.png)

![Pac-Man Screenshot](images/k3.jpg)

🧠 Learn & Modify

This project demonstrates:

* Using Python ncurses for terminal UI
* Handling keyboard input and non-blocking game loops
* Basic game structure: map loading, entity movement, collision detection
* Code that is Python 3.8+ and 2.7+ compatible
* Code that can also run on a Kindle 3 Keyboard

Ideas for contributions:

* Find better characters for ghosts, pacman, fruit etc.
* Slow the ghosts after eating a power pill
* Ramp ghost eating score per original game, i.e. 200, 400, 600 etc.
* Add sounds or different level maps
* Add high score screen with persistence

🪪 License

This project is licensed under the MIT License — see LICENSE for details.
You’re free to use, modify, and distribute it with attribution.

💬 Contributing

Pull requests are welcome! For small improvements:

* Fork the repo
* Create a new branch (git checkout -b feature-name)
* Commit your changes (git commit -m "Add feature")
* Push and open a Pull Request

If you want, open an issue first to discuss larger changes.

🔖 Version History

v1.0.0 – Initial public release
