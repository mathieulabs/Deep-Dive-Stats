# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""What each chart shows, in a few words: the "?" next to its title (hover to read it), and
the widget gallery's tile tooltips. Settings > General can hide the "?"
(Config.SHOW_CHART_HELP)."""

from ....i18n import N_, tr, tr_name

HELP = {
    "activity": N_(
        "How many reviews you did each day. Breakdown by Type splits each bar into:\n"
        "• Learning: new cards still in their learning steps\n"
        "• Relearning: forgotten cards going through relearning\n"
        "• Young: cards with an interval under 21 days\n"
        "• Mature: cards with an interval of 21 days or more\n"
        "• Filtered: reviews in filtered decks that don't change the schedule"
    ),
    "retention": N_(
        "How often you didn't press Again, day by day.\n"
        "• All: every answer, learning steps included\n"
        "• Young: cards with an interval of 1 to 20 days\n"
        "• Mature: cards with an interval of 21 days or more\n"
        "• True: young and mature together, without learning steps. It's the same as Anki's True Retention."
    ),
    "distribution": N_(
        "Which answer buttons you pressed in the period.\n"
        "• Learning: cards in learning or relearning\n"
        "• Young: cards with an interval under 21 days\n"
        "• Mature: cards with an interval of 21 days or more"
    ),
    "card_counts": N_("How your cards are split between new, learning, relearning, young, mature, suspended and buried."),
    "hourly": N_("Your reviews by hour of the day, and how often you passed at each hour."),
    "future_due": N_("How many cards come due on each of the next days. Backlog shows the cards that are overdue.\n"
                     "Breakdown by Type splits them into learning, young and mature cards.\n"
                     "Breakdown by Result shows how many FSRS expects you to pass or fail."),
    "review_intervals": N_("Your cards by their current interval, the number of days until their next review."),
    "stability": N_("Your cards by FSRS stability, the number of days until your chance of remembering them drops to 90%."),
    "difficulty": N_("Your cards by FSRS difficulty, from easiest to hardest to remember."),
    "retrievability": N_("Your cards by FSRS retrievability, your chance of remembering each one right now."),
    "ratings": N_("Which answer buttons you pressed each day. Show as % gives each button's share of the day. Time shows the time spent on each button instead of the number of reviews."),
    "answer_time": N_("Your reviews by how long you took to answer, one bar per second up to 60 seconds, split by rating. By Card Type splits them into learning, young and mature cards instead."),
    "interval_ratings": N_("Your reviews by the card's interval when you answered, split by rating. Learning steps aren't counted."),
    "fsrs_calibration": N_("Your review answers by the recall FSRS predicted just before them (from the memory state after the previous review), passed or failed. With Show as %, the share passed in each bar should fall inside its range when the predictions are right. The memory states are Anki's own, with your presets' current parameters; only reviews a day or more apart count, and nothing with FSRS off."),
    "forgetting_curve": N_("Your review answers by the days since the card's previous review divided by its stability then, passed or failed; the mark on each bar is where FSRS expected the failed part to end. With Show as %, the share passed is the forgetting curve seen in all your reviews: at 1, FSRS expects 90%; past 1, the cards reviewed late. Unlike the First Forgetting Curves, every review counts, not only the first after a card's first rating. The memory states are Anki's own, with your presets' current parameters; only reviews a day or more apart count, and nothing with FSRS off."),
    "fsrs_fatigue": N_("How far FSRS's predictions are off by the place of the answer in its day: the 1st review of the day, the 2nd, and so on. Each bar is the gap between the share of answers passed and the recall FSRS predicted (over several places, their RMSE). Every review of the day counts for the place, whatever its deck; only reviews a day or more apart count, and nothing with FSRS off. A gap that grows late in the day hints at a daily review limit."),
    "stability_increase": N_("Your cards by how much their stability would grow if you answered Good on their due day (x2: it doubles), with the FSRS parameters and desired retention of their preset. A click on a bar opens its cards in the browser. The cards as they are now, whatever the period; nothing with FSRS off."),
    "leech_detector": N_("Your cards by how unlikely their lapses are, given the recall FSRS predicted before each review (two days or more apart). Cards on the right failed far more often than FSRS expected: leeches in the making. A click on a bar opens its cards in the browser. The whole history of the cards counts, whatever the period; nothing with FSRS off."),
    "first_forgetting": N_("How your cards were recalled at their first review on a later day, by the rating of their very first answer. Each dot is the share passed at that interval (its size: the cards in it); the line is the FSRS forgetting curve that fits them best, with its stability. The whole history of the deck's cards counts, whatever the period; a card reset starts over. Under the plot: the longest interval shown and the most dots per rating."),
    "first_forgetting_short": N_("How your cards were recalled at their next answer within a day of their very first one, by its rating (Easy left out): the learning steps. Each dot is the share passed after that many minutes (its size: the cards in it); the line is the FSRS forgetting curve that fits them best, with its stability in minutes. The whole history of the deck's cards counts, whatever the period."),
    "future_retention": N_("The cards due each day ahead, split by the recall FSRS expects when they come due: shown as a percentage, the retention to expect each day. A day with a low share passed is a day of many lapses ahead. Overdue cards are left out; nothing with FSRS off. The period chosen does not change it: today and up to a year ahead."),
    "rating_fatigue": N_("Your reviews by their place in the day: the 1st review of the day, the 2nd, and so on, split by rating. Every review of the day counts for the place, whatever its deck. Show as % shows whether you press Again more often as the day's reviews add up."),
    "sibling_ratings": N_("Reviews of mature cards by the days since a sibling (another card of the same note) was last answered, split by rating. 0 d is the same day. Only counted when that sibling was mature too; young cards and learning steps aren't counted. Show as % shows whether a sibling seen lately makes the answer easier."),
    "resets": N_("The cards you reset to new each day (Forget in the browser), split by what they were before: learning, young or mature."),
    "forgotten": N_("Young and mature cards you answered Again, each day."),
    "todays_retention": N_("How the first answer of each card went on each day of the period: passed (Hard, Good, Easy) or failed (Again). Its later answers that day are not counted. Pick a kind of cards in the header. The stats give the period before too (Show Change from Period Before puts the change in points in the ring); the mark on the ring is the desired retention of FSRS (Show FSRS Target shows or hides it)."),
    "introduced_load": N_("The reviews a day that the cards introduced each day bring now (1 / interval of each card). Shows which days of new cards still cost you reviews."),
    "memorised": N_("How many cards you knew on each past day: the sum of each card's probability of recall then (a card you were sure to recall counts 1, one you would recall half the time counts 0.5). The memory states are Anki's own, with your presets' current parameters; cards count once they have a memory state, and nothing with FSRS off. Deleted cards aren't counted."),
    "stability_trend": N_("The average stability of your cards on each past day: how many days it takes their recall to fall to 90%. The memory states are Anki's own, after each review, with your presets' current parameters. Cards count once they have a memory state; with FSRS off the chart is empty. Deleted cards aren't counted."),
    "load_trend": N_("The reviews a day your cards asked for on each past day (1 / interval of each review card), worked out from your review history. Shows how your daily workload grew. Deleted cards aren't counted."),
    "introduced": N_("New cards you saw for the first time each day. Re-introduced counts cards seen again after a reset. By First Rating shows the answer you gave that first time."),
    "interval_load": N_("How many reviews a day the cards of each interval add on average. A card with a 10-day interval adds 0.1 reviews a day."),
    "lapse_distribution": N_("Your cards by how many times you forgot them. Total Lapses counts their lapses, Load the reviews a day they bring now (1 / interval)."),
    "card_states": N_("How your cards were split between states on each past day, worked out from your review history. Deleted cards aren't counted."),
    "custom_pie": N_("Your own searches, as typed in the browser: a slice each, with the cards of the deck it finds, or their load, lapses or reviews (Value). Edit Searches... in the chart's options. A click on a slice opens its search in the browser. The cards as they are now, whatever the period."),
    "custom_bar": N_("Your own searches, as typed in the browser: the reviews of the cards each one finds in the deck, day by day, or their time (Value). Edit Searches... in the chart's options. A card found by two searches counts in both."),
    "bw_matrix": N_("How well FSRS predicts your recall, by the card's stability (rows) and difficulty (columns) before the answer: the share of answers passed minus the recall FSRS predicted. In the Easy colour: you remember more than predicted; in the Again colour: less. Cells with too few reviews stay empty. The whole history, whatever the period; nothing with FSRS off."),
    "sxr_heatmap": N_("Your review cards now, by their FSRS stability (rows) and retrievability (columns). The darker the cell, the more cards. A click on a cell opens its cards in the browser."),
    "week_hours": N_("Your reviews by day of the week and hour. The darker the cell, the more reviews. By Day shows each day of the period instead."),
    "stability_history": N_("Your cards by the stability FSRS gave them on a day in the past (the first day of the period chosen; today for all time), as Card Stability shows them today. The memory states are Anki's own, with your presets' current parameters; cards with no memory state yet that day aren't counted, nor are cards deleted since."),
    "difficulty_history": N_("Your cards by the difficulty FSRS gave them on a day in the past (the first day of the period chosen; today for all time), as Card Difficulty shows them today. The memory states are Anki's own, with your presets' current parameters; cards with no memory state yet that day aren't counted, nor are cards deleted since."),
    "interval_history": N_("Your review cards by the interval they had on a day in the past (the first day of the period chosen; today for all time), as Review Intervals shows them today. Cards in learning or relearning that day aren't counted, nor are cards whose history was deleted."),
    "time_distribution": N_("Your cards by the time you spent on each one over all its reviews, one bar per second (an hour or more in the last bar). Total Time shows the time those cards took instead of how many they are."),
    "learning_steps": N_("How many learning answers each card needed before it became a review card, counted since its last reset if it had one. Cards still in learning aren't counted, and cards that skipped learning are counted separately."),
    "heatmap": N_("Your reviews on each day of the calendar. The darker the cell, the more reviews, and future days show the cards due.\n"
                  "YRS shows every year one under the other, \u221e the months in a row, 365 the last 365 days and Y one calendar year.\n"
                  "Click a level in the legend to hide it, or click a day to see its cards in the Browser."),
    "added": N_("New cards added to your collection each day."),
    "review_speed": N_("How many seconds a review took on average, each day."),
    "review_distribution": N_("Your cards by how many times you reviewed them. Total Reviews counts their reviews, Load the reviews a day they bring now (1 / interval)."),
    "due_today": N_("Learning cards due today, by the hour they come due. \"Due now\" in the stats: the cards due at this moment, plus the ones Anki lets you learn ahead."),
}


# Charts whose explanation ends with a credit to the add-on they are based on (README, Credits).
SSE_BASED = frozenset((
    "custom_bar", "custom_pie", "first_forgetting", "first_forgetting_short", "fsrs_calibration",
    "fsrs_fatigue", "future_retention", "interval_history", "introduced", "introduced_load",
    "lapse_distribution", "leech_detector", "learning_steps", "load_trend", "memorised", "rating_fatigue",
    "resets", "review_distribution", "sibling_ratings", "stability_increase", "stability_trend",
    "sxr_heatmap", "bw_matrix", "time_distribution", "todays_retention",
))


# Charts easy to misread: a word of caution after their explanation.
CAVEATS = {
    "leech_detector": N_("Experimental."),
    "sibling_ratings": N_("Read it with Rating by Interval: a card's interval also changes its ratings, and siblings seen lately often have short intervals."),
    "rating_fatigue": N_("The order in which your cards are shown changes it: if new or hard cards come last, the Again of late places may come from them, not from fatigue."),
    "fsrs_fatigue": N_("A hint, not a measure: the late places have few reviews, so a single heavy day can weigh a lot."),
}


def sse_credit():
    return tr("Based on {addon} by {author}.", addon="Search Stats Extended", author="Luc McGrady")


def help_text(chart_type):
    """The explanation of a chart type, translated ("" when there is none)."""
    key = str(chart_type or "")
    text = HELP.get(key)
    if not text:
        return ""
    text = tr_name(text)
    if key in CAVEATS:
        text += "\n\n" + tr_name(CAVEATS[key])
    return text + "\n\n" + sse_credit() if key in SSE_BASED else text
