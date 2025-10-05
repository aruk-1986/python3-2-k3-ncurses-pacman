#!/usr/bin/env python
# pacman_kindle.py - Python 2/3 compatible Pac-Man with Kindle-specific rendering mode
# Drop this next to your pacman-map.txt and run with "python pacman_kindle.py"

from __future__ import print_function
import curses
import time
import random
import os

# Simple Point class instead of namedtuple for Python 2 compatibility
class Point(object):
    def __init__(self, y, x):
        self.y = y
        self.x = x

    def __eq__(self, other):
        return hasattr(other, 'y') and hasattr(other, 'x') and self.y == other.y and self.x == other.x

    def __hash__(self):
        return hash((self.y, self.x))

    def __repr__(self):
        return "Point(%r, %r)" % (self.y, self.x)


class GameObject(object):
    def __init__(self, y, x, char):
        self.y = y
        self.x = x
        self.char = char
        self.dy = 0
        self.dx = 0


class Ghost(GameObject):
    def __init__(self, y, x, char='n'):
        GameObject.__init__(self, y, x, char)
        self.frightened = False
        self.frightened_time = 0


class PacMan(GameObject):
    def __init__(self, y, x, char='c'):
        GameObject.__init__(self, y, x, char)
        self.next_dy = 0
        self.next_dx = 0


class Game(object):
    def __init__(self, stdscr, map_file):
        self.stdscr = stdscr
        self.map_file = map_file
        self.load_map(map_file)
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.won = False
        self.power_mode_time = 0
        self.pellets_remaining = 0
        self.speed = 0.15

        # Level system
        self.level = 1
        self.extra_life_awarded = False

        # Fruit mechanics
        self.fruit_spawn_time = 0
        self.fruit_active = False
        self.dots_eaten = 0
        self.fruit_triggered_70 = False
        self.fruit_triggered_170 = False

        # Initialize game objects
        self.pacman = None
        self.ghosts = []
        self.fruit = None
        self.pellets = set()
        self.power_pills = set()
        self.initial_pellets = set()
        self.initial_power_pills = set()
        self.initial_fruit = None

        # Warp tunnel positions
        self.warp_left = None  # Position of '<'
        self.warp_right = None  # Position of '>'

        # Store starting positions
        self.pacman_start = None
        self.ghost_starts = []

        # detect kindle mode: exact TERM == 'xterm' per your request
        self.kindle_mode = (os.environ.get('TERM') == 'xterm')

        self.parse_map()

        # Setup colors with safe fallbacks; but if kindle_mode, we'll ignore colours/attrs for moving entities
        self.have_colors = False
        try:
            if curses.has_colors() and not self.kindle_mode:
                curses.start_color()
                try:
                    curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Pacman
                    curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLACK)    # Walls
                    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)   # Pellets
                    curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)     # Ghosts
                    curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Frightened ghosts
                    curses.init_pair(6, curses.COLOR_MAGENTA, curses.COLOR_BLACK) # Fruit
                    curses.init_pair(7, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Power pills
                    self.have_colors = True
                except Exception:
                    self.have_colors = False
        except Exception:
            self.have_colors = False

        # Attempt to keep ACS_CKBOARD, fallback only if it isn't present at runtime
        self.wall_acsch = None
        try:
            self.wall_acsch = curses.ACS_CKBOARD
        except Exception:
            self.wall_acsch = None

        # Previous positions for erase-before-draw logic
        self.prev_pacman_pos = None
        self.prev_ghost_positions = []

    def load_map(self, map_file):
        try:
            f = open(map_file, 'r')
            lines = f.readlines()
            f.close()
        except Exception:
            lines = []

        self.original_map = [list(line.rstrip('\\n')) for line in lines]
        self.height = len(self.original_map)
        self.width = 0
        for row in self.original_map:
            if len(row) > self.width:
                self.width = len(row)

        # Pad rows to equal width
        for row in self.original_map:
            while len(row) < self.width:
                row.append(' ')

    def parse_map(self):
        for y, row in enumerate(self.original_map):
            for x, char in enumerate(row):
                if char == 'c':
                    self.pacman_start = Point(y, x)
                    self.pacman = PacMan(y, x, char='C')
                    self.original_map[y][x] = ' '
                elif char == 'n':
                    self.ghost_starts.append(Point(y, x))
                    self.ghosts.append(Ghost(y, x, char='W'))
                    self.original_map[y][x] = ' '
                elif char == '@':
                    self.fruit = Point(y, x)
                    self.initial_fruit = Point(y, x)
                    self.original_map[y][x] = ' '
                elif char == '<':
                    self.warp_left = Point(y, x)
                    self.original_map[y][x] = ' '
                elif char == '>':
                    self.warp_right = Point(y, x)
                    self.original_map[y][x] = ' '
                elif char == '.':
                    self.pellets.add(Point(y, x))
                    self.initial_pellets.add(Point(y, x))
                elif char == 'o':
                    self.power_pills.add(Point(y, x))
                    self.initial_power_pills.add(Point(y, x))

        self.pellets_remaining = len(self.pellets) + len(self.power_pills)
        # initialize prev ghost positions list
        self.prev_ghost_positions = [None] * len(self.ghosts)

    def draw_tile_at(self, y, x):
        """Draw the background tile at y,x (pellet, power pill, fruit or blank).
        Used to erase old moving-entity positions cleanly."""
        if y is None or x is None:
            return
        try:
            pos = Point(y, x)
            # Fruit has priority over pellet/power pill in drawing (if active)
            if self.fruit and self.fruit_active and pos.y == self.fruit.y and pos.x == self.fruit.x:
                attr = (curses.color_pair(6) if self.have_colors else 0)
                self.stdscr.addch(y, x, ord('*'), attr)
                return
            if pos in self.power_pills:
                # Power pills: use bold on non-kindle, plain on kindle
                attr = (curses.color_pair(7) | curses.A_BOLD) if self.have_colors else (curses.A_BOLD if not self.kindle_mode else 0)
                self.stdscr.addch(y, x, ord('O'), attr)
                return
            if pos in self.pellets:
                attr = curses.color_pair(3) if self.have_colors else 0
                self.stdscr.addch(y, x, ord('.'), attr)
                return
            # Default blank
            self.stdscr.addch(y, x, ord(' '))
        except Exception:
            # ignore draw errors (out of range, etc.)
            pass

    def draw(self):
        try:
            self.stdscr.erase()
        except Exception:
            pass

        # Draw map
        for y, row in enumerate(self.original_map):
            for x, char in enumerate(row):
                try:
                    if char == '#':
                        # Kindle mode: draw bold space to emulate solid block
                        if self.kindle_mode:
                            try:
                                self.stdscr.addch(y, x, ord(' '), curses.A_BOLD)
                            except Exception:
                                # fallback to '#'
                                self.stdscr.addch(y, x, ord('#'))
                        else:
                            # Normal terminal: try ACS_CKBOARD then '#'
                            if self.wall_acsch is not None:
                                try:
                                    attr = curses.color_pair(2) if self.have_colors else 0
                                    self.stdscr.addch(y, x, self.wall_acsch, attr)
                                except Exception:
                                    self.stdscr.addch(y, x, ord('#'))
                            else:
                                self.stdscr.addch(y, x, ord('#'))
                    elif char == ' ':
                        self.stdscr.addch(y, x, ord(' '))
                except Exception:
                    pass

        # Draw pellets/power pills/fruit (background layer)
        for pellet in list(self.pellets):
            try:
                attr = curses.color_pair(3) if self.have_colors else 0
                self.stdscr.addch(pellet.y, pellet.x, ord('.'), attr)
            except Exception:
                pass

        for pill in list(self.power_pills):
            try:
                # Power pills: use bold on non-kindle, plain on kindle
                attr = (curses.color_pair(7) | curses.A_BOLD) if self.have_colors else (curses.A_BOLD if not self.kindle_mode else 0)
                self.stdscr.addch(pill.y, pill.x, ord('O'), attr)
            except Exception:
                pass

        if self.fruit and self.fruit_active:
            try:
                attr = curses.color_pair(6) if self.have_colors else 0
                self.stdscr.addch(self.fruit.y, self.fruit.x, ord('*'), attr)
            except Exception:
                pass

        # Draw ghosts: erase their previous positions, then draw them in new positions
        # Ensure prev_ghost_positions has an entry for each ghost (safety for any runtime changes)
        if len(self.prev_ghost_positions) < len(self.ghosts):
            self.prev_ghost_positions.extend([None] * (len(self.ghosts) - len(self.prev_ghost_positions)))
        for i, ghost in enumerate(self.ghosts):
            prev = self.prev_ghost_positions[i]
            # erase old position (draw background there)
            if prev is not None:
                self.draw_tile_at(prev.y, prev.x)

        # Now draw all ghosts at their current positions
        for ghost in self.ghosts:
            try:
                if ghost.frightened:
                    # frightened: cyan on normal terminals; on kindle we draw plain character
                    attr = curses.color_pair(5) if (self.have_colors and not self.kindle_mode) else 0
                    self.stdscr.addch(ghost.y, ghost.x, ord('M'), attr)
                else:
                    # On kindle_mode don't use bold/colour for moving entities
                    attr = (curses.color_pair(4) | curses.A_BOLD) if (self.have_colors and not self.kindle_mode) else 0
                    self.stdscr.addch(ghost.y, ghost.x, ord('W'), attr)
            except Exception:
                pass

        # Pacman: erase previous cell then draw at new pos
        if self.prev_pacman_pos is not None:
            self.draw_tile_at(self.prev_pacman_pos.y, self.prev_pacman_pos.x)
        if self.pacman:
            try:
                attr = (curses.color_pair(1) | curses.A_BOLD) if (self.have_colors and not self.kindle_mode) else 0
                self.stdscr.addch(self.pacman.y, self.pacman.x, ord('C'), attr)
            except Exception:
                pass

        # Draw score and lives at top (centered)
        score_str = "Score: %d - Level: %d - Lives: %d" % (self.score, self.level, self.lives)
        try:
            sx = max(0, (self.width - len(score_str)) // 2)
            self.stdscr.addstr(0, sx, score_str, curses.A_BOLD if not self.kindle_mode else 0)
        except Exception:
            pass

        if self.game_over:
            msg = "GAME OVER - Hit R to restart, Q to quit"
            try:
                sx = max(0, (self.width - len(msg)) // 2)
                self.stdscr.addstr(self.height // 2, sx, msg, curses.A_BOLD if not self.kindle_mode else 0)
            except Exception:
                pass

        if self.won:
            msg = "LEVEL UP - Hit SPACE to continue, Q to quit"
            try:
                sx = max(0, (self.width - len(msg)) // 2)
                self.stdscr.addstr(self.height // 2, sx, msg, curses.A_BOLD if not self.kindle_mode else 0)
            except Exception:
                pass

        try:
            self.stdscr.refresh()
        except Exception:
            pass

    def is_wall(self, y, x):
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.original_map[y][x] == '#'
        return True

    def is_valid_move(self, y, x):
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.original_map[y][x] != '#'
        return False

    def move_pacman(self):
        if not self.pacman:
            return

        # Store ACTUAL previous position before any movement
        old_y = self.pacman.y
        old_x = self.pacman.x

        # Try to change direction if new direction pressed
        if self.pacman.next_dy != 0 or self.pacman.next_dx != 0:
            new_y = self.pacman.y + self.pacman.next_dy
            new_x = self.pacman.x + self.pacman.next_dx

            if self.is_valid_move(new_y, new_x):
                self.pacman.dy = self.pacman.next_dy
                self.pacman.dx = self.pacman.next_dx
                self.pacman.next_dy = 0
                self.pacman.next_dx = 0

        # Continue in current direction
        if self.pacman.dy != 0 or self.pacman.dx != 0:
            new_y = self.pacman.y + self.pacman.dy
            new_x = self.pacman.x + self.pacman.dx

            # Check if we're at a warp tunnel entrance
            current_pos = Point(self.pacman.y, self.pacman.x)
            if self.warp_left and self.warp_right:
                if current_pos == self.warp_left and self.pacman.dx < 0:
                    # Warp from left to right
                    self.pacman.y = self.warp_right.y
                    self.pacman.x = self.warp_right.x
                    # Update previous position for next draw
                    self.prev_pacman_pos = Point(old_y, old_x)
                    return
                elif current_pos == self.warp_right and self.pacman.dx > 0:
                    # Warp from right to left
                    self.pacman.y = self.warp_left.y
                    self.pacman.x = self.warp_left.x
                    # Update previous position for next draw
                    self.prev_pacman_pos = Point(old_y, old_x)
                    return

            # Normal movement
            if self.is_valid_move(new_y, new_x):
                self.pacman.y = new_y
                self.pacman.x = new_x
            else:
                # Hit a wall, stop
                self.pacman.dy = 0
                self.pacman.dx = 0

        # Update previous position AFTER all movement logic
        self.prev_pacman_pos = Point(old_y, old_x)

        # Check for pellet collection
        pos = Point(self.pacman.y, self.pacman.x)
        if pos in self.pellets:
            try:
                self.pellets.remove(pos)
            except Exception:
                pass
            self.score += 10
            self.pellets_remaining -= 1
            self.dots_eaten += 1
            self.check_extra_life()

            # Check for fruit spawn triggers
            if self.dots_eaten == 70 and not self.fruit_triggered_70:
                self.spawn_fruit()
                self.fruit_triggered_70 = True
            elif self.dots_eaten == 170 and not self.fruit_triggered_170:
                self.spawn_fruit()
                self.fruit_triggered_170 = True

        # Check for power pill
        if pos in self.power_pills:
            try:
                self.power_pills.remove(pos)
            except Exception:
                pass
            self.score += 50
            self.pellets_remaining -= 1
            self.dots_eaten += 1
            self.check_extra_life()

            # Check for fruit spawn triggers
            if self.dots_eaten == 70 and not self.fruit_triggered_70:
                self.spawn_fruit()
                self.fruit_triggered_70 = True
            elif self.dots_eaten == 170 and not self.fruit_triggered_170:
                self.spawn_fruit()
                self.fruit_triggered_170 = True

            self.power_mode_time = time.time()
            for ghost in self.ghosts:
                ghost.frightened = True

        # Check for fruit
        if self.fruit and self.fruit_active and pos.y == self.fruit.y and pos.x == self.fruit.x:
            self.score += 100
            self.fruit_active = False
            self.check_extra_life()

        # Check win condition
        if self.pellets_remaining == 0:
            self.won = True

    def check_extra_life(self):
        """Award extra life at 10,000 points"""
        if not self.extra_life_awarded and self.score >= 10000:
            self.lives += 1
            self.extra_life_awarded = True

    def next_level(self):
        """Advance to the next level"""
        self.level += 1
        self.won = False
        self.power_mode_time = 0

        # Reset fruit mechanics for new level
        self.fruit_spawn_time = 0
        self.fruit_active = False
        self.dots_eaten = 0
        self.fruit_triggered_70 = False
        self.fruit_triggered_170 = False

        # Reset pellets and power pills to initial state
        self.pellets = set([p for p in self.initial_pellets])
        self.power_pills = set([p for p in self.initial_power_pills])
        self.pellets_remaining = len(self.pellets) + len(self.power_pills)

        # Reset fruit to initial position (but not active)
        if hasattr(self, 'initial_fruit') and self.initial_fruit:
            self.fruit = self.initial_fruit

        # Reset positions
        self.reset_positions()

        # Increase difficulty slightly (make ghosts a bit faster)
        try:
            self.speed = max(0.08, self.speed - 0.01)
        except Exception:
            self.speed = self.speed

    def spawn_fruit(self):
        """Spawn the fruit and start the 10-second timer"""
        if self.initial_fruit:
            self.fruit_active = True
            self.fruit_spawn_time = time.time()

    def update_fruit(self):
        """Check if fruit timer has expired"""
        if self.fruit_active and time.time() - self.fruit_spawn_time > 10:
            self.fruit_active = False

    def get_valid_directions(self, y, x):
        directions = []
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            new_y, new_x = y + dy, x + dx
            if self.is_valid_move(new_y, new_x):
                directions.append((dy, dx))
        return directions

    def is_junction(self, y, x):
        return len(self.get_valid_directions(y, x)) > 2

    def move_ghosts(self):
        current_time = time.time()

        # Check if power mode expired
        if self.power_mode_time > 0 and current_time - self.power_mode_time > 6:
            self.power_mode_time = 0
            for ghost in self.ghosts:
                ghost.frightened = False

        # Update fruit timer
        self.update_fruit()

        for i, ghost in enumerate(self.ghosts):
            # Store ACTUAL old position BEFORE moving
            old_ghost_y = ghost.y
            old_ghost_x = ghost.x

            # Initialize ghost movement if not moving
            if ghost.dy == 0 and ghost.dx == 0:
                directions = self.get_valid_directions(ghost.y, ghost.x)
                if directions:
                    ghost.dy, ghost.dx = random.choice(directions)

            # Random chance to change direction at junction
            if self.is_junction(ghost.y, ghost.x) and random.random() < 0.3:
                directions = self.get_valid_directions(ghost.y, ghost.x)
                # Remove opposite direction
                if directions:
                    opposite = (-ghost.dy, -ghost.dx)
                    newdirs = []
                    for d in directions:
                        if d != opposite:
                            newdirs.append(d)
                    if newdirs:
                        ghost.dy, ghost.dx = random.choice(newdirs)

            # Try to move
            new_y = ghost.y + ghost.dy
            new_x = ghost.x + ghost.dx

            # Check if we're at a warp tunnel entrance
            current_pos = Point(ghost.y, ghost.x)
            if self.warp_left and self.warp_right:
                if current_pos == self.warp_left and ghost.dx < 0:
                    # Warp from left to right
                    ghost.y = self.warp_right.y
                    ghost.x = self.warp_right.x
                    # Update previous position for next draw
                    if len(self.prev_ghost_positions) > i:
                        self.prev_ghost_positions[i] = Point(old_ghost_y, old_ghost_x)
                    # Check collision after warp
                    if self.check_ghost_collision_with_crossing(ghost, old_ghost_y, old_ghost_x):
                        self.handle_collision(ghost)
                        if self.game_over:
                            return
                    continue
                elif current_pos == self.warp_right and ghost.dx > 0:
                    # Warp from right to left
                    ghost.y = self.warp_left.y
                    ghost.x = self.warp_left.x
                    # Update previous position for next draw
                    if len(self.prev_ghost_positions) > i:
                        self.prev_ghost_positions[i] = Point(old_ghost_y, old_ghost_x)
                    # Check collision after warp
                    if self.check_ghost_collision_with_crossing(ghost, old_ghost_y, old_ghost_x):
                        self.handle_collision(ghost)
                        if self.game_over:
                            return
                    continue

            # Normal movement
            if self.is_valid_move(new_y, new_x):
                ghost.y = new_y
                ghost.x = new_x

                # Check for collision after each ghost moves (including crossing detection)
                if self.check_ghost_collision_with_crossing(ghost, old_ghost_y, old_ghost_x):
                    self.handle_collision(ghost)
                    if self.game_over:
                        return
            else:
                # Hit a wall, choose new random direction
                directions = self.get_valid_directions(ghost.y, ghost.x)
                if directions:
                    ghost.dy, ghost.dx = random.choice(directions)

            # Update previous position AFTER all movement logic for this ghost
            if len(self.prev_ghost_positions) > i:
                self.prev_ghost_positions[i] = Point(old_ghost_y, old_ghost_x)

    def check_collisions(self):
        if not self.pacman:
            return

        for ghost in list(self.ghosts):
            # Check if they occupy the same position
            if ghost.y == self.pacman.y and ghost.x == self.pacman.x:
                self.handle_collision(ghost)
                return

    def check_ghost_collision_with_crossing(self, ghost, old_ghost_y, old_ghost_x):
        """Check if pacman and ghost crossed paths (edge case detection)"""
        if not self.pacman:
            return False

        # Check if they're now at the same position
        if ghost.y == self.pacman.y and ghost.x == self.pacman.x:
            return True

        # Check if they crossed paths (swapped positions)
        # This happens when they move towards each other and pass through
        pacman_old_y = self.pacman.y - self.pacman.dy
        pacman_old_x = self.pacman.x - self.pacman.dx

        # Did pacman move from where ghost is now, and ghost move from where pacman is now?
        if (pacman_old_y == ghost.y and pacman_old_x == ghost.x and
            old_ghost_y == self.pacman.y and old_ghost_x == self.pacman.x):
            return True

        return False

    def handle_collision(self, ghost):
        """Handle collision between pacman and a ghost"""
        if ghost.frightened:
            # Eat ghost
            self.score += 200
            # Respawn ghost at its starting position
            try:
                ghost_index = self.ghosts.index(ghost)
                if ghost_index < len(self.ghost_starts):
                    # Clear the previous position before respawning
                    if ghost_index < len(self.prev_ghost_positions):
                        self.prev_ghost_positions[ghost_index] = Point(ghost.y, ghost.x)
                    ghost.y = self.ghost_starts[ghost_index].y
                    ghost.x = self.ghost_starts[ghost_index].x
            except Exception:
                pass
            ghost.frightened = False
            ghost.dy = 0
            ghost.dx = 0
        else:
            # Lose a life
            if self.lives > 0:
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
                else:
                    # Reset positions
                    self.reset_positions()

    def reset_positions(self):
        # Reset pacman to starting position
        if self.pacman_start:
            # Store current position as previous before resetting
            if self.pacman:
                self.prev_pacman_pos = Point(self.pacman.y, self.pacman.x)
            self.pacman.y = self.pacman_start.y
            self.pacman.x = self.pacman_start.x

        self.pacman.dy = 0
        self.pacman.dx = 0
        self.pacman.next_dy = 0
        self.pacman.next_dx = 0

        # Reset ghosts to their starting positions
        for i, ghost in enumerate(self.ghosts):
            # Store current position as previous before resetting
            if i < len(self.prev_ghost_positions):
                self.prev_ghost_positions[i] = Point(ghost.y, ghost.x)
            
            if i < len(self.ghost_starts):
                ghost.y = self.ghost_starts[i].y
                ghost.x = self.ghost_starts[i].x
            ghost.dy = 0
            ghost.dx = 0
            ghost.frightened = False

        self.power_mode_time = 0

    def reset_game(self):
        # Reset game state
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.won = False
        self.power_mode_time = 0
        self.level = 1
        self.extra_life_awarded = False

        # Reset fruit mechanics
        self.fruit_spawn_time = 0
        self.fruit_active = False
        self.dots_eaten = 0
        self.fruit_triggered_70 = False
        self.fruit_triggered_170 = False

        # Reset pellets and power pills to initial state
        self.pellets = set([p for p in self.initial_pellets])
        self.power_pills = set([p for p in self.initial_power_pills])
        self.pellets_remaining = len(self.pellets) + len(self.power_pills)

        # Reset fruit to initial position
        if hasattr(self, 'initial_fruit') and self.initial_fruit:
            self.fruit = self.initial_fruit

        # Reset speed
        self.speed = 0.15

        # Clear previous positions
        self.prev_pacman_pos = None
        self.prev_ghost_positions = [None] * len(self.ghosts)

        # Reset positions
        self.reset_positions()

    def run(self):
        # Non-blocking input and basic setup
        try:
            # Hide cursor for Kindle (bypass curses buffer)
            if self.kindle_mode:
                import sys
                sys.stdout.write("\033[?25l")
                sys.stdout.flush()

            self.stdscr.nodelay(1)
            self.stdscr.keypad(1)
            curses.curs_set(0)
        except Exception:
            pass

        last_move_time = time.time()

        while True:
            current_time = time.time()

            # Handle input
            try:
                key = self.stdscr.getch()
            except Exception:
                key = -1

            if key == ord('q') or key == ord('Q'):
                break
            elif key == ord('r') or key == ord('R'):
                if self.game_over or self.won:
                    self.reset_game()
                    last_move_time = time.time()
            elif key == ord(' '):
                if self.won:
                    self.next_level()
                    last_move_time = time.time()
            elif not self.game_over and not self.won:
                if key == curses.KEY_UP:
                    self.pacman.next_dy = -1
                    self.pacman.next_dx = 0
                elif key == curses.KEY_DOWN:
                    self.pacman.next_dy = 1
                    self.pacman.next_dx = 0
                elif key == curses.KEY_LEFT:
                    self.pacman.next_dy = 0
                    self.pacman.next_dx = -1
                elif key == curses.KEY_RIGHT:
                    self.pacman.next_dy = 0
                    self.pacman.next_dx = 1

            # Update game state
            if not self.game_over and not self.won:
                if current_time - last_move_time >= self.speed:
                    self.move_pacman()
                    self.move_ghosts()
                    # Final collision check after all movements
                    self.check_collisions()
                    last_move_time = current_time

            self.draw()
            # Small sleep to avoid pegging CPU too hard on Kindle
            try:
                time.sleep(0.02)
            except Exception:
                pass

        # Show cursor on exit (at the very end, after the while loop)
        if self.kindle_mode:
            try:
                import sys
                sys.stdout.write("\033[?25h")
                sys.stdout.flush()
            except Exception:
                pass

def main(stdscr):
    game = Game(stdscr, 'pacman-map.txt')
    game.run()


if __name__ == '__main__':
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
