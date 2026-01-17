# Campaign Hero

**Campaign Hero** is a text-based political strategy game where you play as a candidate for Congress.  
You manage your platform, fundraising, messaging, debates, and coalition across demographic groups to win elections.

This project is an early-stage prototype focused on **systems design**, not realism or ideology.

---

## 🎮 Gameplay Overview

You progress week by week through:
- **Primary election**
- **General election**

Each week you choose one action:
- Fundraise (corporate, grassroots, mixed)
- Canvass / field operations
- Adjust policy platform
- Prepare for debates
- Rest
- Polling memo (view demographic support breakdown)

Debates, scandals, media, and momentum all affect voter support.

---

## 🧠 Core Systems

- **Policy Axes**
    - Econ: socialist → capitalist
    - Social: liberal → conservative
    - Governance: legislative-first → executive-first
    - Tone: message-driven → partisan attack

- **Demographics**
    - Working
    - College
    - Rural
    - Urban
    - Seniors
    - Youth

Support is tracked **per demographic**, weighted by district composition.

- **Debates & Virality**
    - Strong performances and zingers can generate earned media
    - Aggressive tone increases virality and backlash risk

---

## ▶️ How to Run

### Requirements
- Python 3.9+ (tested on Python 3.14)
- No external dependencies

### Run locally
```bash
python campaign_hero.py
