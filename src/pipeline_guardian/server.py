"""Server entry point for Pipeline Guardian web application."""

import uvicorn


def main():
    """Run the Pipeline Guardian web server."""
    uvicorn.run(
        "pipeline_guardian.web.app:app",
        host="0.0.0.0",
        port=8888,
        reload=False,
    )


if __name__ == "__main__":
    main()
