> [!WARNING]
>
> Work in progress. Issues still present.

<br>

> [!NOTE]
>
> Also, don't say anything about the typo in the username.
> <br>
> I made that years ago and didn't notice until later.
> <br><br>
> <a>
>  <img src="https://media1.tenor.com/m/W3Mmj2Dzm-AAAAAC/screaming-internally-spongebob.gif" alt="Screaming inside :(" width=100>
> </a>

<br>

<div align="center">
  
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Repo Size](https://img.shields.io/github/repo-size/denv3rr/clear)
![GitHub Created At](https://img.shields.io/github/created-at/denv3rr/clear)
![Last Commit](https://img.shields.io/github/last-commit/denv3rr/clear)
![Issues](https://img.shields.io/github/issues/denv3rr/clear)
![Website](https://img.shields.io/website?url=https%3A%2F%2Fseperet.com&label=seperet.com)

  <a>
    <img src="assets/clear_screenshot_welcome_1.png" alt="Screenshot" style="width=50%">
  </a>
</div>

<div align="center">
  <a href="https://seperet.com">
    <img width="100" src=https://github.com/denv3rr/denv3rr/blob/main/IMG_4225.gif/>
  </a>
</div>

---

## Usage

### Quick Start

```pwsh
git clone git@github.com:denv3rr/clear.git --depth 1
cd clear
python run.py
```

### Set Up Finnhub.io API Key

> [!NOTE]
>
> Although the basic Finnhub.io service is currently free,
> some international exchanges require a paid plan.

#### To use stock symbol data from [Finnhub](https://finnhub.io):

1. Create a free account at: [https://finnhub.io/register](https://finnhub.io/register)
   
2. Then go to your [API dashboard](https://finnhub.io/dashboard) to get your API key/token.

#### Update your `.env.example` file and add your API key

3. Change the file name from `.env.example` to just `.env`
   
4. Add your API key to that `.env` file:
   
    ```bash
    # API KEYS
    FINNHUB_API_KEY=your_api_key_here
    ```

> [!WARNING]
>
> Remember not to commit this file if you clone this.

---
