import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save figures to files, no window needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("AppleStore.csv")
FIG_DIR = Path("figures")
OUT_DIR = Path("outputs")

REQUIRED = ["prime_genre", "price", "size_bytes", "user_rating", "rating_count_tot"]
OPTIONAL_NUMERIC = ["lang.num", "sup_devices.num", "ipadSc_urls.num"]
MIN_APPS_PER_GROUP = 30  # ignore very small groups when ranking



def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        sys.exit(
            f"Cannot find {path}. Download the dataset first (see README) "
            "and place the CSV in this folder."
        )
    df = pd.read_csv(path)
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]  # drop index column
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        sys.exit(f"Missing columns: {missing}\nColumns found: {list(df.columns)}")
    return df


def clean(df: pd.DataFrame):
    report = {"rows_raw": len(df)}

    id_col = "id" if "id" in df.columns else None
    df = df.drop_duplicates(subset=id_col)
    report["duplicates_removed"] = report["rows_raw"] - len(df)

    before = len(df)
    df = df.dropna(subset=REQUIRED)
    report["dropped_missing_values"] = before - len(df)

    before = len(df)
    df = df[(df["price"] >= 0) & (df["size_bytes"] > 0)]
    report["dropped_invalid_values"] = before - len(df)

    df = df.copy()
    df["size_mb"] = df["size_bytes"] / 1e6
    df["pricing"] = np.where(df["price"] == 0, "Free", "Paid")
    df["price_band"] = pd.cut(
        df["price"],
        bins=[-0.01, 0, 1.99, 4.99, 9.99, np.inf],
        labels=["Free", "0.01-1.99", "2-4.99", "5-9.99", "10+"],
    )
    df["size_band"] = pd.cut(
        df["size_mb"],
        bins=[0, 50, 100, 200, 500, np.inf],
        labels=["<50 MB", "50-100 MB", "100-200 MB", "200-500 MB", "500+ MB"],
    )

    # A rating of 0 means "not rated yet", so treat it as missing for averages.
    df["user_rating"] = df["user_rating"].where(df["rating_count_tot"] > 0)

    report["rows_clean"] = len(df)
    return df, report



def summarize_by(df: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        df.groupby(column, observed=True)
        .agg(
            apps=("rating_count_tot", "size"),
            median_ratings=("rating_count_tot", "median"),
            mean_user_rating=("user_rating", "mean"),
        )
        .round(2)
    )


def bar_chart(series: pd.Series, title: str, xlabel: str, filename: str):
    fig, ax = plt.subplots(figsize=(8, 5))
    series.sort_values().plot(kind="barh", ax=ax, color="#1F5FA8")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename, dpi=150)
    plt.close(fig)


def column_chart(series: pd.Series, title: str, ylabel: str, filename: str):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    series.plot(kind="bar", ax=ax, color="#1F5FA8")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("")
    plt.setp(ax.get_xticklabels(), rotation=0)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename, dpi=150)
    plt.close(fig)


def correlation_chart(corr: pd.DataFrame, filename: str):
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr.index)), corr.index)
    for i in range(len(corr.index)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=9)
    ax.set_title("Spearman correlation between app features")
    fig.colorbar(image, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename, dpi=150)
    plt.close(fig)



def main():
    FIG_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)

    raw = load_data(DATA_PATH)
    df, report = clean(raw)

    print("Cleaning report")
    for key, value in report.items():
        print(f"  {key}: {value:,}")


    genres = summarize_by(df, "prime_genre").sort_values("apps", ascending=False)
    genres.to_csv(OUT_DIR / "by_genre.csv")
    bar_chart(
        genres["apps"].head(10),
        "Top 10 genres by number of apps",
        "Number of apps",
        "genres_by_app_count.png",
    )
    big_genres = genres[genres["apps"] >= MIN_APPS_PER_GROUP]
    bar_chart(
        big_genres["median_ratings"].nlargest(10),
        f"Genres with the most ratings per app (median, genres with {MIN_APPS_PER_GROUP}+ apps)",
        "Median number of ratings",
        "genres_by_median_ratings.png",
    )


    pricing = summarize_by(df, "pricing")
    pricing.to_csv(OUT_DIR / "free_vs_paid.csv")
    column_chart(
        pricing["median_ratings"],
        "Median number of ratings: free vs paid apps",
        "Median number of ratings",
        "free_vs_paid.png",
    )


    prices = summarize_by(df, "price_band")
    prices.to_csv(OUT_DIR / "by_price_band.csv")
    column_chart(
        prices["median_ratings"],
        "Median number of ratings by price band (USD)",
        "Median number of ratings",
        "ratings_by_price_band.png",
    )


    sizes = summarize_by(df, "size_band")
    sizes.to_csv(OUT_DIR / "by_size_band.csv")
    column_chart(
        sizes["median_ratings"],
        "Median number of ratings by app size",
        "Median number of ratings",
        "ratings_by_size_band.png",
    )


    numeric = ["price", "size_mb", "user_rating", "rating_count_tot"]
    numeric += [c for c in OPTIONAL_NUMERIC if c in df.columns]
    corr = df[numeric].corr(method="spearman").round(2)
    corr.to_csv(OUT_DIR / "correlations.csv")
    correlation_chart(corr, "correlations.png")

    lines = [
        f"Apps analysed: {len(df):,}",
        "Popularity proxy: total number of ratings (the dataset has no download counts).",
    ]
    top_count = genres.iloc[0]
    lines.append(
        f"Most apps: {genres.index[0]} ({int(top_count['apps']):,} apps, "
        f"{top_count['apps'] / len(df):.1%} of all apps)."
    )
    if not big_genres.empty:
        best = big_genres["median_ratings"].idxmax()
        lines.append(
            f"Highest median number of ratings among genres with {MIN_APPS_PER_GROUP}+ apps: "
            f"{best} ({big_genres.loc[best, 'median_ratings']:,.0f})."
        )
    if {"Free", "Paid"} <= set(pricing.index):
        share_free = pricing.loc["Free", "apps"] / len(df)
        lines.append(
            f"Free apps are {share_free:.1%} of the dataset. Median ratings: "
            f"free {pricing.loc['Free', 'median_ratings']:,.0f} vs "
            f"paid {pricing.loc['Paid', 'median_ratings']:,.0f}. Mean user rating: "
            f"free {pricing.loc['Free', 'mean_user_rating']:.2f} vs "
            f"paid {pricing.loc['Paid', 'mean_user_rating']:.2f}."
        )
    lines.append(
        f"Spearman correlation with rating count: price {corr.loc['price', 'rating_count_tot']:.2f}, "
        f"size_mb {corr.loc['size_mb', 'rating_count_tot']:.2f}, "
        f"user_rating {corr.loc['user_rating', 'rating_count_tot']:.2f}."
    )

    (OUT_DIR / "findings.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nFindings")
    for line in lines:
        print(f"  - {line}")
    print(f"\nSaved charts to {FIG_DIR}/ and tables to {OUT_DIR}/")


if __name__ == "__main__":
    main()
