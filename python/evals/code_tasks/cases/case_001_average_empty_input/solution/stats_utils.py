def average(values):
    if not values:
        raise ValueError("average requires a non-empty input")
    return sum(values) / len(values)

