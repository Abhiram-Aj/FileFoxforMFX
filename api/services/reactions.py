REACTIONS = {
    "like": "👍",
    "love": "❤️",
    "dislike": "👎"
}

async def toggle_reaction(
    poster_id,
    user_id,
    reaction
):

    key = f"reactions_{poster_id}"

    data = redis_get(key) or {
        "like": [],
        "love": [],
        "dislike": []
    }

    for r in data:
        if user_id in data[r]:
            data[r].remove(user_id)

    data[reaction].append(user_id)

    redis_set(key, data)

    return data