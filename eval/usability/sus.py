"""SUS score (0 to 100) from one person's 10 answers, each 1 (strongly disagree) to 5 (strongly agree), in question order.

    uv run python eval/usability/sus.py 4 2 4 1 4 2 5 1 4 2      # prints 82.5
"""
import sys


def sus(answers):
    assert len(answers) == 10 and all(1 <= a <= 5 for a in answers), "10 answers, each 1 to 5"
    # questions 1, 3, 5, 7, 9 are good things (agree is good); 2, 4, 6, 8, 10 are bad things (disagree is good)
    return 2.5 * sum(a - 1 if i % 2 == 0 else 5 - a for i, a in enumerate(answers))


assert sus([5, 1] * 5) == 100 and sus([1, 5] * 5) == 0 and sus([3] * 10) == 50 and sus([4, 2, 4, 1, 4, 2, 5, 1, 4, 2]) == 82.5

if __name__ == "__main__":
    print(sus([int(a) for a in sys.argv[1:]]))
