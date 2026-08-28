import uvicorn

from .config import settings


def run() -> None:
    uvicorn.run(
        "dana.http:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    run()
