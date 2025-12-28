import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# === Ustawienia ===
DATA_DIR = Path("/home/tymek/Desktop/project/data")

FILE_ATTACK = DATA_DIR / "cleaned_analysis_FlowStatsfile_tcp-syn.csv"
FILE_NORMAL = DATA_DIR / "cleaned_analysis_FlowStatsfile_normal.csv"

MAX_PLOT_SAMPLES = 100000

# Ujednolicony styl wykresów
plt.style.use("default")
sns.set_style("whitegrid")
sns.set_context("talk")

COLORS = {
    "Atak TCP-SYN": "#d62728",
    "Poprawny ruch TCP":  "#1f77b4",
    "Poprawny ruch HTTP": "#ff7f0e"
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

# Wczytanie danych
df_attack = pd.read_csv(FILE_ATTACK)
df_normal_all = pd.read_csv(FILE_NORMAL)

# Filtrowanie ruchu TCP z normalnego + wydzielenie HTTP
df_tcp_normal_all = df_normal_all[df_normal_all["ip_proto"] == 6].copy()

http_mask = (
    (df_tcp_normal_all["tp_dst"] == 8080) |
    (df_tcp_normal_all["tp_src"] == 8080)
)

df_http_normal = df_tcp_normal_all[http_mask].copy()
df_tcp_normal = df_tcp_normal_all[~http_mask].copy()

# Usuwanie przepływów inicjujących
def remove_zero_deltas(df):
    mask = (
        (df["delta_pkts"] == 0) &
        (df["delta_bytes"] == 0)
    )
    removed = int(mask.sum())
    return df[~mask].copy(), removed

df_attack, rem_a = remove_zero_deltas(df_attack)
df_tcp_normal, rem_t = remove_zero_deltas(df_tcp_normal)
df_http_normal, rem_h = remove_zero_deltas(df_http_normal)

# Tworzenie nowych cech
def add_features(df):
    df = df.copy()
    df["avg_pkt_size"] = df["bytecount"] / df["pktcount"].replace(0, np.nan)
    df["pkt_per_sec"] = df["pktcount"] / df["dur"].replace(0, np.nan)
    return df.fillna(0)

df_attack = add_features(df_attack)
df_tcp_normal = add_features(df_tcp_normal)
df_http_normal = add_features(df_http_normal)

def safe_describe(df, cols):
    present = [c for c in cols if c in df.columns]
    return df[present].describe().T if present else pd.DataFrame()

# Wybieranie kluczowych cech do zestawienia statystycznego
stats_cols = [
    "pkt_per_sec", "avg_pkt_size",
    "pktcount", "bytecount",
    "delta_pkts", "delta_bytes"
]

# Generowanie raportów statystycznych dla ruchu TCP i HTTP
print("=== Statystyka opisowa: TCP-SYN atak ===")
print(safe_describe(df_attack, stats_cols), "\n")

print("=== Statystyka opisowa: TCP normalny ===")
print(safe_describe(df_tcp_normal, stats_cols), "\n")

print("=== Statystyka opisowa: HTTP normalny ===")
print(safe_describe(df_http_normal, stats_cols), "\n")

# === Funkcja przygotowująca serię do wykresów KDE ===
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

# --- GENEROWANIE WYKRESÓW DLA TCP ---

# Porównywanie intensywności pakietów (Atak vs Normalny)
plot_kde(
    [df_attack, df_tcp_normal, df_http_normal],
    ["Atak TCP-SYN", "Poprawny ruch TCP", "Poprawny ruch HTTP"],
    "pkt_per_sec",
    "title_attack",
    "rys_intensywnosc_tcp_syn.png"
)

# Porównywanie średniej wielkości pakietu
plot_kde(
    [df_attack, df_tcp_normal, df_http_normal],
    ["Atak TCP-SYN", "Poprawny ruch TCP", "Poprawny ruch HTTP"],
    "avg_pkt_size",
    "title_attack",
    "rys_srednia_wielkosc_pakietu_tcp_syn.png"
)

# Analizowanie całkowitej liczby pakietów
plot_kde(
    [df_attack, df_tcp_normal, df_http_normal],
    ["Atak TCP-SYN", "Poprawny ruch TCP", "Poprawny ruch HTTP"],
    "pktcount",
    "title_all",
    "rys_liczba_pakietow_tcp_syn.png"
)

# Analizowanie całkowitej objętości bajtów
plot_kde(
    [df_attack, df_tcp_normal, df_http_normal],
    ["Atak TCP-SYN", "Poprawny ruch TCP", "Poprawny ruch HTTP"],
    "bytecount",
    "title_all",
    "rys_liczba_bajtow_tcp_syn.png"
)
