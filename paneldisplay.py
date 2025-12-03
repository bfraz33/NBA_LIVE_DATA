from PIL import Image, ImageDraw, ImageFont
import os


def load_team_logo(team_abbr, logos_dir="logos"):
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

  
    arena = game.get("arena", "arena: N/A")
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
    scheduled_time = game.get("scheduled_time", "TBD")


    print("PANEL scheduled_time:", scheduled_time, "| status:", display_status)


    away_logo = load_team_logo(away_abbr)
    home_logo = load_team_logo(home_abbr)

    if away_logo is None:
        away_logo = Image.new("RGBA", (24, 24), (128, 128, 128, 255))
    if home_logo is None:
        home_logo = Image.new("RGBA", (24, 24), (128, 128, 128, 255))


    image.paste(away_logo, (0, 4), away_logo)
    image.paste(home_logo, (WIDTH - 24, 4), home_logo)


    draw.text((2, 32), away_record, font=font, fill="white")
    draw.text((WIDTH - 30, 32), home_record, font=font, fill="white")


    live_keywords = ["in progress", "live", "q1", "q2", "q3", "q4", "final", "win", "ot"]
    if any(k in display_status.lower() for k in live_keywords):
        draw.text((30, 12), str(away_score), font=font, fill="white")
        draw.text((WIDTH - 54, 12), str(home_score), font=font, fill="white")


    center_x = WIDTH // 2

    lines = []

 
    status_lower = display_status.lower()
    is_pregame = any(
        key in status_lower
        for key in ["not started", "scheduled", "pregame"]
    )

    if is_pregame:
   
        lines.append(f"Tipoff: {scheduled_time}")   

    else:

        lines.append(display_status)              

    lines.append(ou_string)                      
    lines.append(f"{home_abbr} {ml_string}")      
    lines.append(arena)                           

    start_y = 0
    line_height = 10
    for i, text in enumerate(lines):
        draw.text(
            (center_x - 40, start_y + i * line_height),
            text,
            font=font,
            fill="white",
        )

    image.show()
    return image
