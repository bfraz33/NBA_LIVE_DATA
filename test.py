from client import date, get_games

d = date()
print("Testing date:", d)

games = get_games(d)
print("Type of games:", type(games))
print("Number of games:", len(games))
print("Sample game:")

if games:
    print(games[0])
else:
    print("NO GAMES RETURNED")
