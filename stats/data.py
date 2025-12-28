import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

DATA_DIR = Path("/home/tymek/Desktop/project/data")

files = {
    "icmp": "cleaned_analysis_FlowStatsfile_icmp.csv",
    "land": "cleaned_analysis_FlowStatsfile_land.csv",
    "normal": "cleaned_analysis_FlowStatsfile_normal.csv",
    "tcp-syn": "cleaned_analysis_FlowStatsfile_tcp-syn.csv",
    "udp": "cleaned_analysis_FlowStatsfile_udp.csv"
}

def remove_zero_delta(df):
    # Definiowanie maski dla przepływów zerowych (brak aktywności)
    zero_mask = (
        (df["delta_pkts"] == 0) &
        (df["delta_bytes"] == 0)
    )
    return df[~zero_mask]

results = []

for label, filename in files.items():
    path = DATA_DIR / filename
    try:
        df = pd.read_csv(path)
        count_before = len(df)
        df_after = remove_zero_delta(df)
        count_after = len(df_after)

        # Obliczanie stopnia redukcji danych dla poszczególnych plików
        removed = count_before - count_after
        results.append([label, count_before, count_after, removed])

        print(f"{label:8s}: przed={count_before:,}  po={count_after:,}  usunięto={removed:,}")

    except Exception as e:
        print(f"Błąd przy przetwarzaniu {filename}: {e}")

summary_df = pd.DataFrame(results, columns=["Typ ruchu", "Przed czyszczeniem", "Po czyszczeniu", "Usunięte"])
summary_df = summary_df.set_index("Typ ruchu").sort_values("Przed czyszczeniem", ascending=False)

polskie_nazwy = {
    "tcp-syn": "Atak TCP SYN",
    "udp": "Atak UDP",
    "icmp": "Atak ICMP",
    "land": "Atak LAND",
    "normal": "Ruch normalny"
}

summary_df = summary_df.rename(index=polskie_nazwy)

print("\n=== PODSUMOWANIE ===")
print(summary_df)

summary_df[["Przed czyszczeniem", "Po czyszczeniu", "Usunięte"]] = \
    summary_df[["Przed czyszczeniem", "Po czyszczeniu", "Usunięte"]].astype(int)

# Wizualizowanie danych w skali logarytmicznej
ax = summary_df[["Przed czyszczeniem", "Po czyszczeniu"]].plot(
    kind="bar",
    logy=True,
    figsize=(9,6),
    color=["#4C72B0", "#55A868"]
)

plt.title("Porównanie liczby rekordów przed i po usunięciu przepływów z deltą = 0")
plt.ylabel("Liczba rekordów (skala logarytmiczna)")
plt.xlabel("Typ ruchu")
plt.grid(axis='y', linestyle='--', alpha=0.6)
plt.xticks(rotation=25, ha="right")

for container in ax.containers:
    ax.bar_label(container, fmt="%.0f", label_type="edge", padding=3)

plt.tight_layout()
plt.savefig("wykres_liczba_rekordow_przed_po.png", dpi=300, bbox_inches="tight")
plt.show()
