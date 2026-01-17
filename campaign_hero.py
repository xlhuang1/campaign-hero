import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ----------------------------
# Data models
# ----------------------------

DEMO_KEYS = ["working", "college", "rural", "urban", "seniors", "youth"]

# Each demo has an "ideal" stance on each axis (0..100).
# This is not about real-world accuracy—it's your game's balancing knobs.
# Ideal policy stances by demographic (0..100)
# Econ: socialist -> capitalist
# Social: liberal -> conservative
# Governance: legislative -> executive
# Tone: message-driven -> partisan attack

DEMO_IDEALS = {
    "working": {
        "econ": 35,        # pro-worker, skeptical of pure capitalism
        "social": 55,      # mixed / culturally moderate
        "governance": 65,  # wants things to get done
        "tone": 65,        # responds to forceful, combative messaging
    },
    "college": {
        "econ": 45,        # regulated capitalism
        "social": 20,      # strongly liberal
        "governance": 40,  # prefers process / institutions
        "tone": 25,        # dislikes partisan attack
    },
    "rural": {
        "econ": 55,        # small-business capitalism
        "social": 70,      # socially conservative
        "governance": 60,  # executive authority valued
        "tone": 70,        # likes fighters
    },
    "urban": {
        "econ": 40,        # mixed economy
        "social": 15,      # very liberal
        "governance": 45,  # institutional bias
        "tone": 35,        # prefers rhetoric over attacks
    },
    "seniors": {
        "econ": 50,        # stability over ideology
        "social": 60,      # mildly conservative
        "governance": 70,  # strong executive preference
        "tone": 30,        # dislikes harsh attacks
    },
    "youth": {
        "econ": 30,        # anti-corporate
        "social": 10,      # very liberal
        "governance": 35,  # skeptical of authority
        "tone": 60,        # likes sharp messaging & dunking
    },
}

PARTY_ARCHETYPES = {
    # 0..100 axes:
    # econ: socialist -> capitalist
    # social: liberal -> conservative
    # governance: legislative -> executive
    # tone: message-driven -> partisan attack
    "D":   {"econ": 40, "social": 25, "governance": 45, "tone": 40},
    "R":   {"econ": 70, "social": 75, "governance": 65, "tone": 65},
    "IND": {"econ": 50, "social": 50, "governance": 50, "tone": 45},
}

# How much each demo cares about “party-brand mismatch”
DEMO_PARTY_LOYALTY = {
    "working": 0.9,
    "college": 1.1,
    "rural": 1.0,
    "urban": 1.0,
    "seniors": 1.0,
    "youth": 0.8,
}

DEMO_SENSITIVITY = {
    "working": 1.00,
    "college": 1.10,
    "rural": 1.00,
    "urban": 1.05,
    "seniors": 0.95,
    "youth": 1.10,
}

@dataclass
class District:
    name: str
    partisan_lean: float  # + favors your party, - favors opponent (range approx -0.25..+0.25)
    media_intensity: float  # 0.8..1.3
    volatility: float  # 0.8..1.3
    demos: Dict[str, float]  # weights sum to 1.0
    turnout_base: float  # 0.45..0.65

    def describe(self) -> str:
        top = sorted(self.demos.items(), key=lambda x: x[1], reverse=True)[:3]
        top_str = ", ".join(f"{k}:{int(v*100)}%" for k, v in top)
        lean = "leans you" if self.partisan_lean > 0.05 else ("leans opponent" if self.partisan_lean < -0.05 else "toss-up")
        return (
            f"District: {self.name} ({lean})\n"
            f"  Top demos: {top_str}\n"
            f"  Media intensity: {self.media_intensity:.2f} | Volatility: {self.volatility:.2f} | Turnout base: {self.turnout_base:.2f}"
        )


@dataclass
class Candidate:
    name: str
    party: str
    charisma: int
    discipline: int
    empathy: int
    stamina: int
    cash: int = 50
    momentum: float = 0.0
    fatigue: int = 0

    # Policy positions on axes (0..100), used lightly for now
    econ: int = 50
    social: int = 50
    governance: int = 50
    tone: int = 50  # higher = more aggressive, lower = more inspirational/soft

    def clamp(self) -> None:
        self.cash = max(0, self.cash)
        self.momentum = max(-10.0, min(10.0, self.momentum))
        self.fatigue = max(0, min(10, self.fatigue))
        for attr in ["econ", "social", "governance", "tone"]:
            v = getattr(self, attr)
            setattr(self, attr, max(0, min(100, v)))


@dataclass
class Opponent:
    name: str
    archetype: str
    skill: int  # 30..80
    scandal_risk: float  # 0.0..1.0


@dataclass
class GameState:
    district: District
    you: Candidate
    opponent: Opponent

    week: int = 1
    phase: str = "PRIMARY"  # PRIMARY or GENERAL
    weeks_in_phase: int = 6
    support_by_demo: Dict[str, float] = field(default_factory=dict)
    prepared: bool = False
    name_id: float = 0.20  # name recognition (0..1)
    enthusiasm: float = 0.50  # affects turnout and canvass effectiveness (0..1)
    earned_media: float = 0.00  # temporary weekly boost from virality (0..1)
    history: List[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.history.append(msg)


# ----------------------------
# Utilities / Helpers
# ----------------------------

def rclamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def roll(mu: float, sigma: float = 1.0) -> float:
    return random.gauss(mu, sigma)

def pct(x: float) -> str:
    return f"{x*100:.1f}%"

def platform_fit_score(candidate: Candidate, demo: str) -> float:
    """
    Returns a fit score in [-1, +1] where +1 is perfect match with demo ideals.
    """
    ideals = DEMO_IDEALS[demo]
    # Average absolute distance across axes, normalized to 0..1
    dist = (
                   abs(candidate.econ - ideals["econ"]) +
                   abs(candidate.social - ideals["social"]) +
                   abs(candidate.governance - ideals["governance"]) +
                   abs(candidate.tone - ideals["tone"])
           ) / 4.0  # 0..100
    mismatch = dist / 100.0  # 0..1
    fit = 1.0 - mismatch     # 1..0
    # Map 0..1 -> -1..+1 centered so "meh" isn't neutral
    return (fit * 2.0) - 1.0

def initial_support_by_demo(district: District, you: Candidate) -> Dict[str, float]:
    """
    Creates per-demo support starting point. Overall support emerges from district weights.
    """
    out: Dict[str, float] = {}
    mismatch = party_platform_mismatch(you)  # 0..1
    max_penalty = 0.04

    for demo in DEMO_KEYS:
        fit = platform_fit_score(you, demo) * DEMO_SENSITIVITY[demo]
        base = 0.47 + district.partisan_lean * 0.35

        demo_support = base + (0.06 * fit)

        # Party-brand mismatch penalty (off-brand candidates look "inauthentic")
        loyalty = DEMO_PARTY_LOYALTY[demo]
        size = 0.6 + 0.8 * district.demos[demo]
        demo_support -= mismatch * max_penalty * loyalty * size

        out[demo] = rclamp(demo_support, 0.20, 0.80)

    return out

def overall_support(district: District, support_by_demo: Dict[str, float]) -> float:
    return sum(district.demos[d] * support_by_demo[d] for d in DEMO_KEYS)

def party_platform_mismatch(c: Candidate) -> float:
    """
    Returns mismatch in [0..1]. 0 = perfectly on-brand for party.
    """
    party = (c.party or "IND").upper()
    if party not in PARTY_ARCHETYPES:
        party = "IND"
    arch = PARTY_ARCHETYPES[party]

    dist = (
                   abs(c.econ - arch["econ"]) +
                   abs(c.social - arch["social"]) +
                   abs(c.governance - arch["governance"]) +
                   abs(c.tone - arch["tone"])
           ) / 4.0  # 0..100
    return dist / 100.0  # 0..1

def party_brand_effect_by_demo(gs: GameState) -> Dict[str, float]:
    """
    Produces per-demo support adjustments based on party-platform consistency.
    Negative when you're off-brand (e.g. very progressive 'R').
    """
    m = party_platform_mismatch(gs.you)  # 0..1
    # Tuning knob: max penalty at full mismatch ~ -4% per demo (scaled by loyalty)
    max_penalty = 0.04

    out: Dict[str, float] = {}
    for demo in DEMO_KEYS:
        loyalty = DEMO_PARTY_LOYALTY[demo]
        # Stronger effect for larger demos in the district
        size = 0.6 + 0.8 * gs.district.demos[demo]
        out[demo] = -(m * max_penalty * loyalty * size)
    return out

def district_lean_label(d: District) -> str:
    if d.partisan_lean > 0.10:
        return "leans you"
    if d.partisan_lean > 0.03:
        return "tilts you"
    if d.partisan_lean < -0.10:
        return "leans opponent"
    if d.partisan_lean < -0.03:
        return "tilts opponent"
    return "toss-up"

def environment_capsule(d: District) -> str:
    if d.media_intensity >= 1.20:
        media = "Loud media"
    elif d.media_intensity <= 0.90:
        media = "Quiet media"
    else:
        media = "Normal media"

    if d.volatility >= 1.20:
        vol = "high volatility"
    elif d.volatility <= 0.90:
        vol = "low volatility"
    else:
        vol = "medium volatility"

    if d.turnout_base >= 0.60:
        turnout = "high-turnout"
    elif d.turnout_base <= 0.50:
        turnout = "low-turnout"
    else:
        turnout = "mid-turnout"

    return f"{media} • {vol} • {turnout} district"


def stance_word(value: int, left: str, right: str) -> str:
    # 0..100 -> left / center-ish / right
    if value <= 33:
        return left
    if value >= 67:
        return right
    return "moderate"


def candidate_pitch(c: Candidate) -> str:
    econ = stance_word(c.econ, "socialist-leaning", "capitalist-leaning")
    social = stance_word(c.social, "liberal", "conservative")
    gov = stance_word(c.governance, "legislative-first", "executive-first")
    tone = stance_word(c.tone, "message-driven", "attack-focused")

    # Slightly nicer phrasing when "moderate"
    def soften(word: str, axis: str) -> str:
        if word != "moderate":
            return word
        return {
            "econ": "economically moderate",
            "social": "socially moderate",
            "gov": "institutional",
            "tone": "measured",
        }[axis]

    econ = soften(econ, "econ")
    social = soften(social, "social")
    gov = soften(gov, "gov")
    tone = soften(tone, "tone")

    return f"{tone}, {gov} candidate — {econ}, {social} platform."



# ----------------------------
# Generators
# ----------------------------

def gen_district(difficulty: str) -> District:
    # Difficulty adjusts partisan lean, volatility, media intensity
    diff = difficulty.strip().lower()
    if diff not in {"easy", "normal", "hard"}:
        diff = "normal"

    if diff == "easy":
        partisan_lean = random.uniform(0.05, 0.20)
        media_intensity = random.uniform(0.85, 1.10)
        volatility = random.uniform(0.85, 1.10)
        turnout_base = random.uniform(0.52, 0.65)
    elif diff == "hard":
        partisan_lean = random.uniform(-0.20, -0.05)
        media_intensity = random.uniform(1.05, 1.30)
        volatility = random.uniform(1.05, 1.30)
        turnout_base = random.uniform(0.45, 0.58)
    else:
        partisan_lean = random.uniform(-0.05, 0.05)
        media_intensity = random.uniform(0.90, 1.20)
        volatility = random.uniform(0.90, 1.20)
        turnout_base = random.uniform(0.48, 0.62)

    # Demographics
    weights = [random.random() for _ in DEMO_KEYS]
    s = sum(weights)
    demos = {k: w / s for k, w in zip(DEMO_KEYS, weights)}

    names = ["IL-10 Lakeshore", "OH-07 Riverbend", "TX-21 Hill Country", "PA-08 Keystone North", "CA-46 Harborline"]
    return District(
        name=random.choice(names),
        partisan_lean=partisan_lean,
        media_intensity=media_intensity,
        volatility=volatility,
        demos=demos,
        turnout_base=turnout_base,
    )

def gen_opponent(phase: str) -> Opponent:
    # Primary opponent usually weaker than general
    if phase == "PRIMARY":
        archetypes = [
            ("Local Insider", 45, 0.25),
            ("Firebrand", 50, 0.45),
            ("Wealthy Self-Funder", 55, 0.30),
        ]
    else:
        archetypes = [
            ("Seasoned Moderate", 62, 0.20),
            ("Hardline Ideologue", 65, 0.35),
            ("Media-Savvy Populist", 68, 0.45),
        ]
    name_pool = ["Casey Trent", "Morgan Vale", "Jordan Pike", "Riley Hart", "Avery Sloan"]
    a, skill, risk = random.choice(archetypes)
    return Opponent(name=random.choice(name_pool), archetype=a, skill=skill, scandal_risk=risk)


# ----------------------------
# Game mechanics
# ----------------------------

def weekly_decay(gs: GameState) -> None:
    # earned media fades; fatigue drags performance; momentum soft reverts
    gs.earned_media *= 0.35
    gs.enthusiasm = rclamp(gs.enthusiasm - 0.01, 0.2, 0.9)
    gs.you.momentum *= 0.85
    gs.you.fatigue = rclamp(gs.you.fatigue - 0.8, 0, 10)
    gs.you.clamp()

def apply_support_shift(gs: GameState, delta: float, reason: str, demo_weights: Dict[str, float] = None) -> None:
    """
    Applies a support shift across demographics.
    - delta is the "headline" shift.
    - demo_weights optionally biases which demos move more (must sum ~1).
    """
    amp = gs.district.volatility * (1.0 + 0.15 * gs.district.media_intensity)
    pull = gs.district.partisan_lean * 0.010  # small weekly pull

    if demo_weights is None:
        demo_weights = {d: 1.0 / len(DEMO_KEYS) for d in DEMO_KEYS}

    for d in DEMO_KEYS:
        w = demo_weights.get(d, 0.0)
        shift = (delta * amp * w) + (pull * gs.district.demos[d])
        gs.support_by_demo[d] = rclamp(gs.support_by_demo[d] + shift, 0.20, 0.80)

    gs.log(f"{reason} => support {pct(overall_support(gs.district, gs.support_by_demo))}")

def fundraise(gs: GameState, donor_type: str) -> None:
    donor_type = donor_type.lower().strip()
    base = 12 + gs.you.discipline * 0.25 + gs.name_id * 20
    if donor_type == "corporate":
        cash = int(max(0, roll(base + 15, 6)))
        gs.you.cash += cash
        gs.you.momentum -= 0.4
        gs.enthusiasm = rclamp(gs.enthusiasm - 0.03, 0.2, 0.9)
        gs.log(f"Fundraising (corporate): +${cash}k, enthusiasm down a bit.")
    elif donor_type == "grassroots":
        cash = int(max(0, roll(base - 3, 5)))
        gs.you.cash += cash
        gs.you.momentum += 0.3
        gs.enthusiasm = rclamp(gs.enthusiasm + 0.03, 0.2, 0.9)
        gs.log(f"Fundraising (grassroots): +${cash}k, enthusiasm up.")
    else:
        cash = int(max(0, roll(base, 5)))
        gs.you.cash += cash
        gs.log(f"Fundraising (mixed): +${cash}k.")
    gs.you.fatigue = rclamp(gs.you.fatigue + 1.0, 0, 10)
    gs.you.clamp()

def canvass(gs: GameState) -> None:
    # Costs time + some cash, improves name_id and support slightly depending on enthusiasm
    cost = 8
    if gs.you.cash < cost:
        gs.log("Tried to canvass, but you’re too broke to field a ground operation.")
        apply_support_shift(gs, -0.003, "Ground game fizzles")
        return
    gs.you.cash -= cost
    gain = (0.004 + gs.enthusiasm * 0.006) * (1.0 + gs.you.empathy / 140)
    gs.name_id = rclamp(gs.name_id + 0.015, 0.0, 1.0)
    gs.enthusiasm = rclamp(gs.enthusiasm + 0.02, 0.2, 0.9)
    gs.you.momentum += 0.2
    gs.you.fatigue = rclamp(gs.you.fatigue + 1.2, 0, 10)
    field_weights = {"working": 0.35, "youth": 0.30, "urban": 0.15, "rural": 0.15, "college": 0.03, "seniors": 0.02}
    apply_support_shift(gs, gain, "Canvassing + field", demo_weights=field_weights)
    gs.log(f"Canvassing cost ${cost}k. Name ID now {pct(gs.name_id)}.")

def polling(gs: GameState) -> None:
    cost = 6  # $6k for a poll; tune as desired
    if gs.you.cash < cost:
        gs.log("Polling: you can’t afford a real poll. You rely on vibes and anecdotes.")
        print("\nPolling failed: not enough cash.")
        input("Press Enter to continue...")
        return

    gs.you.cash -= cost

    print("\n" + "=" * 60)
    print(f"POLLING MEMO — {gs.phase} (Cost: ${cost}k)")
    print(f"District: {gs.district.name}")
    print("-" * 60)

    overall = overall_support(gs.district, gs.support_by_demo)
    print(f"Overall support (weighted): {pct(overall)}")
    print("\nDemographic breakdown:")
    print(f"{'Demo':<10} {'District%':>9} {'Support':>9} {'Contribution':>13}")
    print("-" * 60)

    # Sort by district share, biggest first
    rows = sorted(gs.district.demos.items(), key=lambda x: x[1], reverse=True)
    for demo, share in rows:
        sup = gs.support_by_demo.get(demo, overall)
        contrib = share * sup
        print(f"{demo:<10} {share*100:>8.1f}% {sup*100:>8.1f}% {contrib*100:>12.2f}%")

    print("-" * 60)
    print("Tip: Focus actions on large demos or the ones you’re underwater with.")
    print("=" * 60 + "\n")

    gs.log(f"Polling conducted (-${cost}k). You review a demographic memo.")
    input("Press Enter to continue...")

def adjust_policy(gs: GameState, axis: str, direction: int) -> None:
    # Small shifts; coherence matters later (for now, affects momentum/enthusiasm lightly)
    axis = axis.lower().strip()
    step = 8 * direction
    if axis not in {"econ", "social", "governance", "tone"}:
        gs.log("Policy team is confused. Nothing changes.")
        return
    old = getattr(gs.you, axis)
    setattr(gs.you, axis, old + step)
    gs.you.clamp()

    # Tone influences zinger potential & backlash risk
    if axis == "tone":
        if direction > 0:
            gs.log("You lean sharper and more combative. Clips potential rises… and so does backlash risk.")
        else:
            gs.log("You lean more hopeful and unifying. Fewer dunks, more trust.")
    else:
        gs.log(f"Policy shift on {axis}: {old} -> {getattr(gs.you, axis)}.")

    gs.you.momentum += 0.15
    gs.you.fatigue = rclamp(gs.you.fatigue + 0.8, 0, 10)

def rest(gs: GameState) -> None:
    gs.you.fatigue = rclamp(gs.you.fatigue - 4.0, 0, 10)
    gs.you.momentum += 0.3
    gs.log("You rest, reset, and do fewer self-inflicted errors this week.")

def prep_debate(gs: GameState) -> None:
    # Improves discipline effect; costs stamina
    gs.you.momentum += 0.10
    gs.you.fatigue = rclamp(gs.you.fatigue + 0.9, 0, 10)
    gs.prepared = True
    gs.log("Debate prep: message drills, oppo research, and rehearsed pivots.")

def maybe_scandal(gs: GameState) -> None:
    # Small chance each week; can hit you or opponent.
    # Higher media intensity + fatigue increases your risk.
    base_you = 0.03 * gs.district.media_intensity + 0.01 * (gs.you.fatigue / 10)
    base_opp = 0.02 * gs.district.media_intensity

    if random.random() < base_you:
        dmg = abs(roll(0.010, 0.006))
        apply_support_shift(gs, -dmg, "Minor scandal hits you")
        gs.you.momentum -= 0.8
        gs.log("A sloppy old quote resurfaces. It’s not fatal, but it’s annoying.")
    if random.random() < base_opp * gs.opponent.scandal_risk:
        gain = abs(roll(0.008, 0.005))
        apply_support_shift(gs, gain, "Opponent stumbles")
        gs.you.momentum += 0.5
        gs.log("Your opponent steps on a rake. You don’t even have to swing.")

def debate(gs: GameState) -> None:
    # If you prepped, you get a real advantage this debate.
    prepared = getattr(gs, "prepared", False)

    # Rescaled: candidate stats (5..25-ish) now generate ~30..80 power.
    you_power = (
            2.5 * gs.you.charisma
            + 2.0 * gs.you.discipline
            + 1.5 * gs.you.empathy
            + 8.0 * gs.you.momentum
            - 3.0 * gs.you.fatigue
    )

    if prepared:
        you_power += 6.0  # tangible prep boost

    # Opponent power stays in the ~40..75 range
    opp_power = gs.opponent.skill + roll(0, 4)

    # Narrower randomness so outcomes track the inputs more
    perf = roll(you_power - opp_power, 6)
    gs.log(f"[DEBUG] debate: you_power={you_power:.1f} opp_power={opp_power:.1f} perf={perf:.1f} prepared={prepared}")

    # Zinger chance increases with charisma + tone (more aggressive) + media intensity
    zinger_chance = rclamp(
        0.10
        + (gs.you.charisma / 200)
        + (gs.you.tone / 250)
        + (0.08 * (gs.district.media_intensity - 1.0)),
        0.05,
        0.60,
        )

    zinger = (random.random() < zinger_chance) and (perf > -8)
    backfire = False

    delta = 0.0
    headline = ""

    if perf > 18:
        delta = 0.020
        headline = "You dominated the debate."
        gs.you.momentum += 1.3
    elif perf > 6:
        delta = 0.010
        headline = "You won the debate."
        gs.you.momentum += 0.7
    elif perf > -6:
        delta = 0.000
        headline = "It was a wash."
        gs.you.momentum += 0.1
    elif perf > -18:
        delta = -0.010
        headline = "You lost the debate."
        gs.you.momentum -= 0.7
    else:
        delta = -0.020
        headline = "You faceplanted on stage."
        gs.you.momentum -= 1.3

    # Zinger adds earned media, may add support, can backfire with low empathy / very high tone
    if zinger:
        viral = rclamp(
            0.12 + (gs.you.tone / 300) + (gs.district.media_intensity - 1.0) * 0.15,
            0.08,
            0.40,
            )
        gs.earned_media = rclamp(gs.earned_media + viral, 0.0, 0.70)

        backfire_chance = rclamp(0.08 + (gs.you.tone / 220) - (gs.you.empathy / 260), 0.02, 0.35)
        backfire = random.random() < backfire_chance

        if backfire:
            delta -= 0.006
            gs.enthusiasm = rclamp(gs.enthusiasm - 0.03, 0.2, 0.9)
            gs.log("Your zinger goes viral… but people also call it mean. Some soft support leaks.")
        else:
            delta += 0.008
            gs.enthusiasm = rclamp(gs.enthusiasm + 0.02, 0.2, 0.9)
            gs.log("You land a zinger that becomes a clip machine. Earned media surges.")

    zinger_weights = {"youth": 0.35, "urban": 0.30, "college": 0.25, "working": 0.05, "rural": 0.03, "seniors": 0.02}
    apply_support_shift(gs, delta, f"Debate night: {headline}", demo_weights=zinger_weights)

    gs.you.fatigue = rclamp(gs.you.fatigue + 1.5, 0, 10)
    gs.you.clamp()

    # Prep is consumed
    if hasattr(gs, "prepared"):
        gs.prepared = False


def paid_media(gs: GameState) -> None:
    # Auto ads: spend a capped fraction of cash, never zeroing out the campaign
    if gs.you.cash < 5:
        return  # too broke to meaningfully advertise

    max_fraction = 0.5  # at most 50% of current cash
    hard_cap = 20       # never more than $20k
    floor_cash = 5      # always leave at least $5k
    min_spend = 3       # don't bother running ads for less than $3k

    affordable = max(0, gs.you.cash - floor_cash)
    spend = min(hard_cap, affordable, int(gs.you.cash * max_fraction))

    if spend < min_spend:
        return

    gs.you.cash -= spend

    eff = (0.004 + (spend / 5000)) * (1.0 + gs.name_id * 0.4)
    apply_support_shift(gs, eff, f"Paid media (${spend}k)")
    gs.log(f"Ads run: spent ${spend}k.")


def earned_media_tick(gs: GameState) -> None:
    if gs.earned_media <= 0:
        return
    bump = 0.004 * gs.earned_media
    apply_support_shift(gs, bump, "Earned media tailwind")
    gs.log(f"Earned media effect this week: +{bump*100:.2f}% support-ish.")


# ----------------------------
# UI / Flow
# ----------------------------

def explain_actions(gs: GameState) -> None:
    debate_weeks = get_debate_weeks(gs.phase, gs.weeks_in_phase)
    debate_str = ", ".join(str(w) for w in debate_weeks) if debate_weeks else "None"

    print("\nACTION EXPLANATIONS")
    print(f"Scheduled debate weeks this phase ({gs.phase}): {debate_str}\n")

    print("  1) Fundraise (corporate)")
    print("     • Usually raises the most cash.")
    print("     • Small enthusiasm hit and momentum hit (you look 'bought').")
    print("     • Good when you need money fast for ads.\n")

    print("  2) Fundraise (grassroots)")
    print("     • Less cash than corporate on average.")
    print("     • Boosts enthusiasm and a bit of momentum (you look authentic).")
    print("     • Good for turnout and building a base.\n")

    print("  3) Fundraise (mixed)")
    print("     • Middle-of-the-road cash with fewer side effects.")
    print("     • Good safe option if you’re unsure.\n")

    print("  4) Canvass / field operation")
    print("     • Costs cash, but improves support through ground game.")
    print("     • Increases enthusiasm and name recognition.")
    print("     • Strong over time, especially in close races.\n")

    print("  5) Policy shift")
    print("     • Nudges your platform (econ/social/governance/tone).")
    print("     • Currently mostly affects momentum and future debate/virality potential.")
    print("     • Tone up = more zinger potential, higher backfire risk.\n")

    print("  6) Debate prep")
    print("     • Helps your debate performance (via momentum/disciplined play).")
    print("     • Adds fatigue (prep is work).")
    print("     • Best used the week BEFORE a scheduled debate.\n")

    print("  7) Rest")
    print("     • Reduces fatigue so you perform better next week.")
    print("     • Slower tempo, but prevents spirals and unforced errors.\n")

    print("  8) Polling memo")
    print("     • Costs cash, consumes the week.")
    print("     • Shows your coalition: per-demo support and how it composes overall support.")
    print("     • Helps you decide whether to persuade or mobilize.\n")

    input("Press Enter to return to actions...")


def get_debate_weeks(phase: str, weeks_in_phase: int) -> List[int]:
    weeks = {3, 5} if phase == "PRIMARY" else {3, 6, 8}
    # Guard in case you ever change phase length
    return sorted([w for w in weeks if 1 <= w <= weeks_in_phase])



def choose_action(gs: GameState) -> None:
    while True:
        print("\nChoose ONE action this week:")
        print("  1) Fundraise (corporate)")
        print("  2) Fundraise (grassroots)")
        print("  3) Fundraise (mixed)")
        print("  4) Canvass / field operation (costs cash)")
        print("  5) Policy shift")
        print("  6) Debate prep")
        print("  7) Rest")
        print("  8) Polling memo (costs cash)")
        print("  9) Explain actions")

        choice = input("> ").strip()
        if choice == "9":
            explain_actions(gs)
            continue  # go back to menu
        if choice in {"1", "2", "3", "4", "5", "6", "7", "8"}:
            break
        print("Enter 1-8.")

    if choice == "1":
        fundraise(gs, "corporate")
    elif choice == "2":
        fundraise(gs, "grassroots")
    elif choice == "3":
        fundraise(gs, "mixed")
    elif choice == "4":
        canvass(gs)
    elif choice == "5":
        policy_menu(gs)
    elif choice == "6":
        prep_debate(gs)
    elif choice == "7":
        rest(gs)
    else:   # 8
        polling(gs)

def policy_menu(gs: GameState) -> None:
    print("\nPolicy shift: pick an axis to nudge (+ or -).")
    print("  econ | social | governance | tone")
    axis = input("Axis> ").strip().lower()

    print("Direction?")
    print("  1) Nudge up (toward 100)")
    print("  2) Nudge down (toward 0)")
    d = input("> ").strip()
    direction = 1 if d == "1" else -1

    adjust_policy(gs, axis, direction)

def print_status(gs: GameState) -> None:
    phase_weeks_left = gs.weeks_in_phase - gs.week + 1
    print("\n" + "=" * 60)
    print(f"Week {gs.week}/{gs.weeks_in_phase} — {gs.phase}")
    overall = overall_support(gs.district, gs.support_by_demo)
    print(f"Support: {pct(overall)} | Cash: ${gs.you.cash}k | Name ID: {pct(gs.name_id)}")
    print(f"Momentum: {gs.you.momentum:+.2f} | Fatigue: {gs.you.fatigue:.1f} | Enthusiasm: {pct(gs.enthusiasm)}")

    print(next_debate_info(gs))
    print(f"Environment: {environment_capsule(gs.district)}")

    if gs.earned_media > 0.01:
        print(f"Earned media (lingering): {gs.earned_media:.2f}")
    print(f"Weeks left in phase: {phase_weeks_left}")
    print("=" * 60)


def describe_environment(d: District) -> str:
    # Media intensity
    if d.media_intensity >= 1.20:
        media = "a high-volume media market"
    elif d.media_intensity >= 1.05:
        media = "a busy media market"
    elif d.media_intensity <= 0.90:
        media = "a quiet media market"
    else:
        media = "a normal media market"

    # Volatility
    if d.volatility >= 1.20:
        vol = "highly volatile"
    elif d.volatility <= 0.90:
        vol = "stable"
    else:
        vol = "moderately volatile"

    return f"{media} and a {vol} electorate"


def print_campaign_kickoff(gs: GameState) -> None:
    d = gs.district
    you = gs.you
    opp = gs.opponent

    overall = overall_support(d, gs.support_by_demo)

    top = sorted(d.demos.items(), key=lambda x: x[1], reverse=True)[:3]
    top_str = ", ".join(f"{k} {int(v*100)}%" for k, v in top)

    debate_weeks = get_debate_weeks(gs.phase, gs.weeks_in_phase)
    debate_str = ", ".join(str(w) for w in debate_weeks) if debate_weeks else "none"

    lean = district_lean_label(d)
    env = environment_capsule(d)
    pitch = candidate_pitch(you)

    print("\n" + "=" * 60)
    print("CAMPAIGN KICKOFF")
    print("=" * 60)
    print(f"{you.name} ({you.party}) is running in {d.name}, a district that {lean}.")
    print(f"{env}. Core blocs: {top_str}.")
    print(f"Your opening pitch: {pitch}")
    print(f"Primary opponent: {opp.name} — {opp.archetype} (skill {opp.skill}).")
    print("-" * 60)
    print(f"Opening support: {pct(overall)} | Name ID: {pct(gs.name_id)} | Cash: ${you.cash}k")
    print(f"Platform values: Econ {you.econ} | Social {you.social} | Gov {you.governance} | Tone {you.tone}")
    print(f"Scheduled debate weeks (PRIMARY): {debate_str}")
    print("=" * 60)
    input("\nPress Enter to begin the campaign...")


def next_debate_info(gs: GameState) -> str:
    debate_weeks = get_debate_weeks(gs.phase, gs.weeks_in_phase)
    future = [w for w in debate_weeks if w >= gs.week]
    if not future:
        return "Next debate: none"
    nxt = future[0]
    if nxt == gs.week:
        return "Next debate: THIS WEEK Tip: Debate Prep or Rest can help this week."
    delta = nxt - gs.week
    return f"Next debate: Week {nxt} (in {delta} week{'s' if delta != 1 else ''})"


def print_recent(gs: GameState, n: int = 5) -> None:
    if not gs.history:
        return
    print("\nRecent events:")
    for line in gs.history[-n:]:
        print(f" - {line}")

def phase_transition(gs: GameState) -> None:
    # Determine primary outcome
    if gs.phase == "PRIMARY":
        print("\nPRIMARY RESULTS")
        overall = overall_support(gs.district, gs.support_by_demo)
        print(f"Final primary support estimate: {pct(overall)}")
        if overall < 0.50:
            print("You lose the primary. Campaign over.")
            raise SystemExit(0)
        print("You win the primary and advance to the general election.\n")
        gs.phase = "GENERAL"
        gs.week = 1
        gs.weeks_in_phase = 8
        gs.opponent = gen_opponent("GENERAL")
        # General resets dynamics a bit
        gs.support_by_demo = initial_support_by_demo(gs.district, gs.you)
        gs.earned_media = 0.0
        gs.history.append(f"New opponent: {gs.opponent.name} ({gs.opponent.archetype}, skill {gs.opponent.skill})")
    else:
        # Election day
        print("\nELECTION DAY")
        turnout = rclamp(gs.district.turnout_base + (gs.enthusiasm - 0.5) * 0.10 + roll(0, 0.02), 0.35, 0.75)
        overall = overall_support(gs.district, gs.support_by_demo)
        final = rclamp(overall + roll(0, 0.015), 0.0, 1.0)
        print(f"Turnout: {pct(turnout)}")
        print(f"Final vote estimate: {pct(final)}")
        if final >= 0.50:
            print("You win! Congratulations, Representative.")
        else:
            print("You lose. The district wasn’t ready—or you weren’t.")
        raise SystemExit(0)

def run_week(gs: GameState) -> None:
    print_status(gs)
    choose_action(gs)

    # Passive effects
    earned_media_tick(gs)
    paid_media(gs)  # always auto-spend a small capped amount for simplicity
    maybe_scandal(gs)

    # Schedule debates (simple): primary weeks 3 & 5; general weeks 3, 6, 8
    debate_weeks = {3, 5} if gs.phase == "PRIMARY" else {3, 6, 8}
    if gs.week in debate_weeks:
        print("\n--- DEBATE NIGHT ---")
        debate(gs)

    weekly_decay(gs)
    print_recent(gs, n=6)

    # Advance week / phase end
    gs.week += 1
    if gs.week > gs.weeks_in_phase:
        phase_transition(gs)


# ----------------------------
# Entry point
# ----------------------------

def make_candidate() -> Candidate:
    print("Welcome to Campaign Hero (prototype).")
    name = input("Candidate name> ").strip() or "Alex Candidate"

    c = Candidate(
        name=name,
        party="IND",
        charisma=5,
        discipline=5,
        empathy=5,
        stamina=5,
    )

    # 1) Platform first
    choose_platform(c)

    # 2) Party second (and party interacts with platform later via mismatch)
    print("\nChoose your party label:")
    print("  D) Democrat")
    print("  R) Republican")
    print("  I) Independent")
    while True:
        p = input("> ").strip().upper()
        if p in {"D", "R", "I", "IND"}:
            c.party = "IND" if p in {"I", "IND"} else p
            break
        print("Enter D, R, or I.")

    m = party_platform_mismatch(c)
    print(f"\nParty-platform consistency: {int((1.0 - m) * 100)}%")
    if m > 0.60:
        print("Warning: Your platform is very off-brand for this party. Expect authenticity penalties.")

    # 3) Stats last
    print("\nAllocate 20 points among stats (charisma, discipline, empathy, stamina).")
    base = {"charisma": 5, "discipline": 5, "empathy": 5, "stamina": 5}
    points = 20

    def ask_stat(k: str) -> int:
        nonlocal points
        while True:
            try:
                v = int(input(f"{k} (current {base[k]}, +0..+{points})> ").strip() or "0")
            except ValueError:
                print("Enter a number.")
                continue
            if 0 <= v <= points:
                points -= v
                return base[k] + v
            print("Out of range.")

    c.charisma = ask_stat("charisma")
    c.discipline = ask_stat("discipline")
    c.empathy = ask_stat("empathy")
    c.stamina = ask_stat("stamina")

    c.clamp()
    print(f"\nRemaining unspent points (auto ignored): {points}")
    return c


def choose_platform(c: Candidate) -> None:
    def ask_axis(label: str, left: str, right: str, description: str) -> int:
        print(f"\n{label} stance")
        print(description)
        print(f"Scale: {left} (0) → {right} (100)")
        while True:
            s = input("Enter value [0–100, default 50]> ").strip()
            if not s:
                return 50
            try:
                v = int(s)
            except ValueError:
                print("Enter a whole number 0–100.")
                continue
            if 0 <= v <= 100:
                return v
            print("Enter a number between 0 and 100.")

    print("\nSet your campaign platform.\nYou will choose each axis one at a time.")

    c.econ = ask_axis(
        label="Econ",
        left="socialist",
        right="capitalist",
        description="Economic policy orientation: public ownership and redistribution vs. market-driven capitalism."
    )

    c.social = ask_axis(
        label="Social",
        left="liberal",
        right="conservative",
        description="Social and cultural policy: progressive social change vs. traditional values."
    )

    c.governance = ask_axis(
        label="Governance",
        left="legislative-first",
        right="executive-first",
        description="Power preference: consensus-building through legislatures vs. decisive executive action."
    )

    c.tone = ask_axis(
        label="Tone",
        left="message-driven",
        right="partisan attack",
        description=(
            "Campaign style: inspirational messaging vs. aggressive partisan confrontation.\n"
            "Higher values increase zinger and virality potential, but also backlash risk."
        )
    )

    c.clamp()


def main() -> None:
    random.seed()  # remove or set a number for deterministic runs

    difficulty = input("Difficulty (easy/normal/hard)> ").strip() or "normal"
    district = gen_district(difficulty)
    you = make_candidate()
    opp = gen_opponent("PRIMARY")

    gs = GameState(district=district, you=you, opponent=opp)

    # Starting support influenced by district lean and candidate charisma
    gs.support_by_demo = initial_support_by_demo(district, you)
    gs.history.append(district.describe())
    gs.history.append(f"Primary opponent: {opp.name} ({opp.archetype}, skill {opp.skill})")

    print_campaign_kickoff(gs)

    while True:
        run_week(gs)

if __name__ == "__main__":
    main()
