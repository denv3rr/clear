import os
os.environ["TTE_DEBUG"] = "0"
from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

# Import used effects
from terminaltexteffects.effects import (
    effect_blackhole,
    effect_burn,
    effect_thunderstorm,
    effect_smoke,
    effect_waves,
)

class TextEffectManager:
    """Manages Terminal Text Effects for application screens."""
    
    def __init__(self, movement_speed: float = 10.0):
        self.console = Console()
        self.speed = movement_speed

    def _panel_to_text(self, renderable) -> str:
        """Render a Rich renderable (like a Panel or Table) to plain, non-ANSI text."""
        # Create a plain text console (no ANSI) so animation receives clean characters
        plain = Console(
            color_system=None,
            width=self.console.width,
            height=self.console.height,
            record=True,
            force_terminal=True
        )

        # Print the renderable to the plain console and capture the output
        with plain.capture() as cap:
            # We must print the renderable aligned as it will appear in the main console
            plain.print(renderable)

        return cap.get()

    def play_effect(self, renderable, effect_class):
        """Applies a specified TerminalTextEffect to a rich renderable object."""
        self.console.clear()
        
        # 1. Convert Rich object to clean, multi-line string text
        text = self._panel_to_text(renderable)
        
        # 2. Instantiate and play the effect
        effect = effect_class(text)
        with effect.terminal_output() as terminal:
            for frame in effect: 
                terminal.print(frame)

    # --------------- PUBLIC ANIMATION FUNCTIONS ---------------
    # https://chrisbuilds.github.io/terminaltexteffects/showroom/

    def play_burn(self, renderable):
        self.play_effect(renderable, effect_burn.Burn)

    def play_thunderstorm(self, renderable):
        self.play_effect(renderable, effect_thunderstorm.Thunderstorm)

    def play_blackhole(self, renderable):
        self.play_effect(renderable, effect_blackhole.Blackhole)

    def play_smoke(self, renderable):
        self.play_effect(renderable, effect_smoke.Smoke)
    
    def play_waves(self, renderable):
        self.play_effect(renderable, effect_waves.Waves)

    # -------- ANIMATION FUNCTIONS END --------