from getpass import getpass
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPE = "https://www.googleapis.com/auth/content"

MERCHANT_ACCOUNT_ID = "5848066126"


def main() -> None:
    print("=== Hermes Commerce Agent / Google Merchant OAuth ===")
    print()
    print("Introduce las credenciales del cliente OAuth.")
    print("No se mostrarán ni se enviarán a ningún sitio excepto Google.")
    print()

    client_id = input("Google OAuth Client ID: ").strip()
    client_secret = getpass("Google OAuth Client Secret: ").strip()

    if not client_id or not client_secret:
        raise RuntimeError("Client ID y Client Secret son obligatorios")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                "http://127.0.0.1"
            ],
        }
    }

    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=[SCOPE],
    )

    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )

    if not credentials.refresh_token:
        raise RuntimeError(
            "Google no devolvió refresh_token"
        )

    output = Path.home() / ".hermes-google-merchant.env"

    output.write_text(
        "\n".join(
            [
                f"GOOGLE_OAUTH_CLIENT_ID={client_id}",
                f"GOOGLE_OAUTH_CLIENT_SECRET={client_secret}",
                (
                    "GOOGLE_OAUTH_REFRESH_TOKEN="
                    f"{credentials.refresh_token}"
                ),
                (
                    "GOOGLE_MERCHANT_ACCOUNT_ID="
                    f"{MERCHANT_ACCOUNT_ID}"
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    print()
    print("OAuth completado correctamente.")
    print(f"Credenciales guardadas en: {output}")
    print()
    print("NO añadas ese archivo a Git.")


if __name__ == "__main__":
    main()
