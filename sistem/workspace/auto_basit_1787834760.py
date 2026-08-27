import pygame
import random
from collections import deque
from typing import List, Tuple, Deque

# --- Constants ---
# Screen dimensions
SCREEN_WIDTH: int = 600
SCREEN_HEIGHT: int = 600

# Grid size for snake segments and food
GRID_SIZE: int = 20
GRID_WIDTH: int = SCREEN_WIDTH // GRID_SIZE
GRID_HEIGHT: int = SCREEN_HEIGHT // GRID_SIZE

# Colors (RGB)
WHITE: Tuple[int, int, int] = (255, 255, 255)
BLACK: Tuple[int, int, int] = (0, 0, 0)
GREEN: Tuple[int, int, int] = (0, 255, 0)
RED: Tuple[int, int, int] = (255, 0, 0)
BLUE: Tuple[int, int, int] = (0, 0, 255)

# Snake speed (frames per second)
SNAKE_SPEED: int = 10

# Directions
UP: Tuple[int, int] = (0, -1)
DOWN: Tuple[int, int] = (0, 1)
LEFT: Tuple[int, int] = (-1, 0)
RIGHT: Tuple[int, int] = (1, 0)

# Type alias for a point (x, y) coordinate
Point = Tuple[int, int]


class Snake:
    """
    Represents the snake in the game.
    Manages its body segments, direction, movement, and collision detection.
    """

    def __init__(self, start_pos: Point) -> None:
        """
        Initializes a new Snake instance.

        Args:
            start_pos: The initial (x, y) grid coordinates for the snake's head.
        """
        self.body: Deque[Point] = deque([start_pos])
        self.direction: Point = RIGHT
        self.grow_pending: bool = False

    def get_head_position(self) -> Point:
        """
        Returns the current grid coordinates of the snake's head.

        Returns:
            A tuple (x, y) representing the head's position.
        """
        return self.body[0]

    def change_direction(self, new_direction: Point) -> None:
        """
        Changes the snake's direction, preventing immediate reverse turns.

        Args:
            new_direction: The new direction vector (e.g., UP, DOWN, LEFT, RIGHT).
        """
        # Prevent changing to the opposite direction
        if (new_direction[0] * -1, new_direction[1] * -1) != self.direction:
            self.direction = new_direction

    def move(self) -> None:
        """
        Moves the snake one step in its current direction.
        If `grow_pending` is True, the snake grows by not removing its tail.
        """
        cur_head: Point = self.get_head_position()
        new_head: Point = (cur_head[0] + self.direction[0], cur_head[1] + self.direction[1])
        self.body.appendleft(new_head)

        if not self.grow_pending:
            self.body.pop()
        else:
            self.grow_pending = False

    def grow(self) -> None:
        """
        Sets a flag to make the snake grow during its next movement.
        """
        self.grow_pending = True

    def check_collision(self) -> bool:
        """
        Checks for collisions with walls or the snake's own body.

        Returns:
            True if a collision occurred, False otherwise.
        """
        head: Point = self.get_head_position()

        # Wall collision
        if not (0 <= head[0] < GRID_WIDTH and 0 <= head[1] < GRID_HEIGHT):
            return True

        # Self-collision (head collides with any part of the body except itself)
        # Note: deque allows efficient access to head (index 0)
        if head in list(self.body)[1:]:  # Convert to list for 'in' check on non-deque types
            return True

        return False

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draws the snake on the given Pygame surface.

        Args:
            surface: The Pygame surface to draw on.
        """
        for segment in self.body:
            pygame.draw.rect(
                surface,
                GREEN,
                (segment[0] * GRID_SIZE, segment[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE),
            )


class Food:
    """
    Represents the food item in the game.
    Manages its position and random placement.
    """

    def __init__(self) -> None:
        """
        Initializes a new Food instance with a random position.
        """
        self.position: Point = (0, 0)
        self.randomize_position([])  # Initial placement

    def randomize_position(self, snake_body: Deque[Point]) -> None:
        """
        Generates a new random position for the food, ensuring it doesn't
        spawn on top of the snake.

        Args:
            snake_body: The current body segments of the snake.
        """
        while True:
            x = random.randint(0, GRID_WIDTH - 1)
            y = random.randint(0, GRID_HEIGHT - 1)
            new_pos: Point = (x, y)
            if new_pos not in snake_body:
                self.position = new_pos
                break

    def get_position(self) -> Point:
        """
        Returns the current grid coordinates of the food.

        Returns:
            A tuple (x, y) representing the food's position.
        """
        return self.position

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draws the food on the given Pygame surface.

        Args:
            surface: The Pygame surface to draw on.
        """
        pygame.draw.rect(
            surface,
            RED,
            (self.position[0] * GRID_SIZE, self.position[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE),
        )


class Game:
    """
    Manages the overall game logic, including initialization, game loop,
    event handling, state updates, and rendering.
    """

    def __init__(self) -> None:
        """
        Initializes the Pygame environment and all game components.
        """
        pygame.init()
        pygame.display.set_caption("Python Snake Game")

        self.screen: pygame.Surface = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.font: pygame.font.Font = pygame.font.Font(None, 36)

        self.snake: Snake
        self.food: Food
        self.score: int
        self.game_over: bool
        self.running: bool

        self._reset_game()

    def _reset_game(self) -> None:
        """
        Resets the game state to its initial configuration.
        Called at the start of a new game or after a game over.
        """
        start_x = GRID_WIDTH // 2
        start_y = GRID_HEIGHT // 2
        self.snake = Snake((start_x, start_y))
        self.food = Food()
        self.food.randomize_position(self.snake.body)  # Ensure food doesn't spawn on initial snake
        self.score = 0
        self.game_over = False
        self.running = True

    def _handle_input(self) -> None:
        """
        Processes user input events (keyboard presses, window close).
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if self.game_over:
                    if event.key == pygame.K_r:  # 'R' to restart
                        self._reset_game()
                    elif event.key == pygame.K_q:  # 'Q' to quit
                        self.running = False
                else:
                    if event.key == pygame.K_UP:
                        self.snake.change_direction(UP)
                    elif event.key == pygame.K_DOWN:
                        self.snake.change_direction(DOWN)
                    elif event.key == pygame.K_LEFT:
                        self.snake.change_direction(LEFT)
                    elif event.key == pygame.K_RIGHT:
                        self.snake.change_direction(RIGHT)

    def _update_game_state(self) -> None:
        """
        Updates the game logic, including snake movement, collision checks,
        and food consumption.
        """
        if self.game_over:
            return

        self.snake.move()

        if self.snake.check_collision():
            self.game_over = True
            return

        # Check if snake eats food
        if self.snake.get_head_position() == self.food.get_position():
            self.snake.grow()
            self.score += 1
            self.food.randomize_position(self.snake.body)

    def _draw_elements(self) -> None:
        """
        Draws all game elements on the screen, including the background,
        snake, food, and score.
        """
        self.screen.fill(BLACK)  # Clear screen

        self.snake.draw(self.screen)
        self.food.draw(self.screen)

        # Draw score
        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(score_text, (10, 10))

        if self.game_over:
            game_over_text = self.font.render("Game Over! Press 'R' to Restart or 'Q' to Quit", True, WHITE)
            text_rect = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(game_over_text, text_rect)

        pygame.display.flip()  # Update the full display Surface to the screen

    def run(self) -> None:
        """
        Starts and runs the main game loop.
        """
        while self.running:
            self._handle_input()
            self._update_game_state()
            self._draw_elements()
            self.clock.tick(SNAKE_SPEED)

        pygame.quit()


if __name__ == '__main__':
    game = Game()
    game.run()