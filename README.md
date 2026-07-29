<div align="center">

# Halo: Campaign Evolved Achievement Bot

A lightweight Discord bot that connects directly to **Xbox Live** and displays your **Halo: Campaign Evolved** achievement progress.
<br>

</div>

---

# Features

- Xbox Live Authentication
- Halo: Campaign Evolved Achievement Tracking
- Achievement Search
- Locked & Unlocked Achievement Lists
- Gamerscore Tracking
- Completion Percentage
- Discord Slash Commands
- Automatic Achievement Refresh

---


## Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/halo-campaign-evolved-achievement-bot.git

cd halo-campaign-evolved-achievement-bot
```

---

## Install dependencies

```bash
pip install -r requirements.txt
```

---

## Create your `.env`

```env
DISCORD_TOKEN=

DISCORD_GUILD_ID=

DISCORD_OWNER_ID=

MICROSOFT_CLIENT_ID=

HALO_CAMPAIGN_EVOLVED_TITLE_ID=2082978535
```

---

## Run

```bash
python bot.py
```

The first launch will prompt you to authenticate your Xbox account using Microsoft's Device Login.

---

# Commands

| Command | Description |
|---------|-------------|
| `/status` | Bot status |
| `/xbox-login` | Login to Xbox |
| `/xbox-logout` | Logout |
| `/achievements` | Overall progress |
| `/locked` | Locked achievements |
| `/unlocked` | Unlocked achievements |
| `/achievement` | Search achievements |
| `/refresh` | Refresh achievement data |

---

# Project Structure

```
Halo_Campaign_Evolved_Achievement_Bot/

├── auth.py
├── xbox.py
├── bot.py
├── requirements.txt
├── .env.example
├── README.md
└── images/
```

---

# Security

Never upload

```
.env
.tokens
```

Your Xbox authentication tokens and Discord Bot Token should always remain private.

---

# Built With

- Python
- discord.py
- MSAL
- Xbox Live REST API
- Requests

---

# Roadmap

- [x] Xbox Authentication
- [x] Achievement Tracking
- [x] Achievement Search
- [x] Slash Commands
- [ ] Rich Discord Embeds
- [ ] Achievement Pagination
- [ ] Unlock Notifications
- [ ] Compare Profiles
- [ ] Achievement Rarity
- [ ] Leaderboards
- [ ] Achievement History

---

<div align="center">

Made with ❤️ for the Halo community.

</div>
