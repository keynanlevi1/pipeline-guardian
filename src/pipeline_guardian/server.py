"""Server entry point for Pipelines Guardian web application."""

import uvicorn


def main():
    """Run the Pipelines Guardian web server."""
    uvicorn.run(
        "pipeline_guardian.web.app:app",
        host="0.0.0.0",
        port=8888,
        reload=False,
    )


if __name__ == "__main__":
    main()
