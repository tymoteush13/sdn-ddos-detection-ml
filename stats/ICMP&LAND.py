import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# === Ustawienia ===
DATA_DIR = Path("/home/tymek/Desktop/project/data")

FILE_ICMP_ATTACK = DATA_DIR / "cleaned_analysis_FlowStatsfile_icmp.csv"
FILE_LAND_ATTACK = DATA_DIR / "cleaned_analysis_FlowStatsfile_land.csv"
FILE_NORMAL = DATA_DIR / "cleaned_analysis_FlowStatsfile_normal.csv"

MAX_PLOT_SAMPLES = 100000

# Ujednolicony styl wykresów
plt.style.use("default")
sns.set_style("whitegrid")
sns.set_context("talk")

COLORS = {
    "Atak ICMP": "#d62728",
    "Atak LAND": "#ff7f0e",
    "Poprawny ruch ICMP": "#1f77b4"
}

LABELS = {
    "pkt_per_sec": {
        "xlabel": "Logarytm liczby pakietów na sekundę [pakiety/s]",
        "title_attack": "Rozkład intensywności ruchu",
        "title_all": "Rozkład intensywności ruchu"
    },
    "avg_pkt_size": {
        "xlabel": "Logarytm średniej wielkości pakietu [B]",
        "title_attack": "Rozkład średniej wielkości pakietu",
        "title_all": "Rozkład średniej wielkości pakietu"
    },
    "pktcount": {
        "xlabel": "Logarytm liczby pakietów w strumieniu [pakiety]",
        "title_all": "Rozkład liczby pakietów w strumieniu"
    },
    "bytecount": {
        "xlabel": "Logarytm liczby bajtów w strumieniu [B]",
        "title_all": "Rozkład liczby bajtów w strumieniu"
    }
}

# Wczytywanie danych
df_icmp_attack = pd.read_csv(FILE_ICMP_ATTACK)
df_land_attack = pd.read_csv(FILE_LAND_ATTACK)
df_normal_all = pd.read_csv(FILE_NORMAL)

# Filtrowanie ruchu ICMP ze zbioru normalnego
df_icmp_normal = df_normal_all[df_normal_all["ip_proto"] == 1].copy()

# Usuwanie przepływów inicjujących
def remove_zero_deltas(df):
    mask = (
        (df["delta_pkts"] == 0) &
        (df["delta_bytes"] == 0)
    )
    removed = int(mask.sum())
    return df[~mask].copy(), removed

df_icmp_attack, rem_icmp = remove_zero_deltas(df_icmp_attack)
df_land_attack, rem_land = remove_zero_deltas(df_land_attack)
df_icmp_normal, rem_norm = remove_zero_deltas(df_icmp_normal)

# Tworzenie nowych cech
def add_features(df):
    df = df.copy()
    df["avg_pkt_size"] = df["bytecount"] / df["pktcount"].replace(0, np.nan)
    df["pkt_per_sec"] = df["pktcount"] / df["dur"].replace(0, np.nan)
    return df.fillna(0)

df_icmp_attack = add_features(df_icmp_attack)
df_land_attack = add_features(df_land_attack)
df_icmp_normal = add_features(df_icmp_normal)

def safe_describe(df, cols):
    present = [c for c in cols if c in df.columns]
    return df[present].describe().T if present else pd.DataFrame()

# Wybieranie kluczowych cech do zestawienia statystycznego
stats_cols = [
    "pkt_per_sec", "avg_pkt_size",
    "pktcount", "bytecount",
    "delta_pkts", "delta_bytes"
]

# Generowanie raportów statystycznych dla ruchu ICMP i LAND
print("=== Statystyka opisowa: ICMP attack ===")
print(safe_describe(df_icmp_attack, stats_cols), "\n")

print("=== Statystyka opisowa: LAND attack ===")
print(safe_describe(df_land_attack, stats_cols), "\n")

print("=== Statystyka opisowa: ICMP normal ===")
print(safe_describe(df_icmp_normal, stats_cols), "\n")

# === Funkcja przygotowująca serię ===
def prepare_series(df, col):
    # Weryfikowanie istnienia kolumny w ramce danych
    if col not in df.columns:
        return pd.Series([], dtype=float)

    # Czyszczenie danych (usuwanie wartości nieskończonych i pustych)
    s = df[col].replace([np.inf, -np.inf], np.nan).dropna()

    # Eliminowanie zer dla specyficznej cechy (wymóg wykresu logarytmicznego)
    if col == "pkt_per_sec":
        s = s[s > 0]

    # Zabezpieczanie przed pustą serią
    if s.empty:
        return s

    # Próbkowanie danych (ograniczanie liczby punktów dla wydajności)
    if len(s) > MAX_PLOT_SAMPLES:
        s = s.sample(MAX_PLOT_SAMPLES, random_state=42)

    return s

# === GENEROWANIE WYKRESÓW ===
def plot_kde(dfs, labels, column, title_key, filename):
    # Inicjowanie figury wykresu
    plt.figure(figsize=(10, 6))

    for df, label in zip(dfs, labels):
        s = prepare_series(df, column)
        if s.empty:
            continue

        # Rysowanie rozkładu gęstości w skali logarytmicznej
        sns.kdeplot(
            np.log1p(s),
            label=label,
            color=COLORS[label],
            fill=True,
            alpha=0.35,
            linewidth=1.5
        )

    # Formatowanie osi i dobieranie tytułu
    plt.xlabel(LABELS[column]["xlabel"])
    plt.ylabel("Gęstość")

    if title_key == "title_attack":
        plt.title(LABELS[column]["title_attack"])
    else:
        plt.title(LABELS[column]["title_all"])

    # Zapisywanie gotowego wykresu do pliku
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.show()

# --- GENEROWANIE WYKRESÓW DLA ICMP ---

# Porównywanie intensywności pakietów (Atak vs Normalny)
plot_kde(
    [df_icmp_attack, df_land_attack, df_icmp_normal],
    ["Atak ICMP", "Atak LAND", "Poprawny ruch ICMP"],
    "pkt_per_sec",
    "title_attack",
    "rys_intensywnosc_pakietow_icmp.png"
)

# Porównywanie średniej wielkości pakietu
plot_kde(
    [df_icmp_attack, df_land_attack, df_icmp_normal],
    ["Atak ICMP", "Atak LAND", "Poprawny ruch ICMP"],
    "avg_pkt_size",
    "title_attack",
    "rys_srednia_wielkosc_pakietu_icmp.png"
)

# Analizowanie całkowitej liczby pakietów
plot_kde(
    [df_icmp_attack, df_land_attack, df_icmp_normal],
    ["Atak ICMP", "Atak LAND", "Poprawny ruch ICMP"],
    "pktcount",
    "title_all",
    "rys_liczba_pakietow_icmp.png"
)

# Analizowanie całkowitej objętości bajtów
plot_kde(
    [df_icmp_attack, df_land_attack, df_icmp_normal],
    ["Atak ICMP", "Atak LAND", "Poprawny ruch ICMP"],
    "bytecount",
    "title_all",
    "rys_liczba_bajtow_icmp.png"
)