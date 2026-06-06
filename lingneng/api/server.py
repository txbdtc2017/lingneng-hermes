from __future__ import annotations

import uvicorn

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings


def main() -> None:
    settings = LingNengSettings.from_env()
    uvicorn.run(
        create_app(settings=settings),
        host=settings.api_host,
        port=settings.api_port,
    )


if __name__ == "__main__":
    main()
