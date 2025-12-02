
from PIL import Image, ImageDraw, ImageFont
import os


def load_team_logo(team_abbr, logos_dir="logos"):
    # Construct expected PNG path
    png_path = os.path.join(logos_dir, f"{team_abbr.upper()}.png")
    print(f"Looking for logo at: {png_path}")
    if os.path.exists(png_path):
        try:
            return Image.open(png_path).convert("RGBA").resize((24, 24))
        except Exception as e:
            print(f"Error loading logo {png_path}: {e}")
    return None

def render_game_to_image(game):
    WIDTH, HEIGHT = 256, 48
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    # Extract game data
    venue = game.get("venue", "Venue: N/A")   
    away = game.get("away", "???")
    home = game.get("home", "???")
    away_score = game.get("away_score", 0)
    home_score = game.get("home_score", 0)
    display_status = game.get("display_status", "")
    ml_string = game.get("ml_string", "ML: N/A") 
    ou_string = game.get("ou_string", "O/U: N/A")
    away_abbr = game.get("away_abbr", away)
    home_abbr = game.get("home_abbr", home)
    away_record = game.get("away_record", "")
    home_record = game.get("home_record", "")

    # Load team logos
    away_logo = load_team_logo(away_abbr)
    home_logo = load_team_logo(home_abbr)

    # Use fallback gray boxes if missing
    if away_logo is None:
        away_logo = Image.new("RGBA", (24, 24), (128, 128, 128, 255))
    if home_logo is None:
        home_logo = Image.new("RGBA", (24, 24), (128, 128, 128, 255))

    # Paste team logos
    image.paste(away_logo, (0, 4), away_logo)
    image.paste(home_logo, (WIDTH - 24, 4), home_logo)

    # Draw records underneath logos
    draw.text((2, 32), away_record, font=font, fill="white")
    draw.text((WIDTH - 30,32), home_record, font=font, fill="white")

    # Display scores next to each team's logo
    if any(keyword in display_status.lower() for keyword in ["in progress", "bot", "top", "mid", "final", "win", "postponed", "delayed"]):
        # Away score (right of away logo)
        draw.text((30, 12), str(away_score), font=font, fill="white")
        # Home score (left of home logo)
        draw.text((WIDTH - 54, 12), str(home_score), font=font, fill="white")

    # Calculate center position for stacked text
    center_x = WIDTH // 2
    
    # Draw stacked information in the center
    draw.text((center_x - 40, 0), display_status, font=font, fill="white")  # Top line: Game status/time
    draw.text((center_x - 40, 10), ou_string, font=font, fill="white")      # Middle line: Over/Under
    draw.text((center_x - 40, 20), f"{home_abbr} {ml_string }", font=font, fill="white")
    draw.text((center_x - 40, 30), venue, font=font, fill="white")          # Venue on its own line

    # Show the image (for testing)
    image.show()

    return image
