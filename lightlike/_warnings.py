import warnings

__all__: list[str] = ["suppress"]


def suppress() -> None:
    warnings.filterwarnings("ignore", category=SyntaxWarning)

    warnings.filterwarnings(
        action="ignore",
        message=(
            "Cannot create BigQuery Storage client, "
            "the dependency google-cloud-bigquery-storage is not installed."
        ),
        category=UserWarning,
    )
