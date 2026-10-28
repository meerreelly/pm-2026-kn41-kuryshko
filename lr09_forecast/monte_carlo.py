"""Monte Carlo прогноз дати релізу: метод зі слайда 21 лекції L5.

Запуск: python3 monte_carlo.py
Дані для кроку 6 (lr09_reference_velocity.csv) лежать у матеріалах курсу,
Drive, home_works/LR09 Прогноз velocity і Monte Carlo/.
"""
import csv
import math
import random


def load_velocity(path):
    with open(path) as f:
        return [float(row["points_done"]) for row in csv.DictReader(f)]


def simulate(velocity_history, remaining_points, simulations=10000, seed=42):
    rnd = random.Random(seed)
    results = []
    for _ in range(simulations):
        remaining = remaining_points
        sprints = 0
        while remaining > 0:
            remaining -= rnd.choice(velocity_history)
            sprints += 1
        results.append(sprints)
    results.sort()

    def percentile_ceil(p):
        idx = min(len(results) - 1, math.ceil(p * len(results)) - 1)
        return results[idx]

    return results, percentile_ceil(0.5), percentile_ceil(0.85)


if __name__ == "__main__":
    ref_path = "lr09_reference_velocity.csv"
    full = load_velocity(ref_path)
    scenarios = [
        ("12 спринтів", full),
        ("спринти 1-2", full[0:2]),
        ("спринти 5-6", full[4:6]),
    ]
    for label, history in scenarios:
        _, p50, p85 = simulate(history, remaining_points=220)
        print(f"{label}: velocity={history}  P50={p50}  P85={p85}  ширина={p85 - p50}")
