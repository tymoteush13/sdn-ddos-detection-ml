import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

DATA_DIR = Path("/home/tymek/Desktop/project/data")
FILE_NORMAL = DATA_DIR / "cleaned_analysis_FlowStatsfile_normal.csv"

plt.style.use("default")
sns.set_style("whitegrid")
sns.set_context("talk")

df_normal_all = pd.read_csv(FILE_NORMAL)
print(f"Wczytano: {len(df_normal_all):,} rekordów\n")

# Klasyfikacja protokołów
def classify_protocol(row):
    proto = row["ip_proto"]
    src = row.get("tp_src", 0)
    dst = row.get("tp_dst", 0)

    if proto == 1:
        return "ICMP"
    elif proto == 17:
        return "UDP"
    elif proto == 6:
        if src in (80, 8080) or dst in (80, 8080):
            return "HTTP (TCP)"
        else:
            return "Pozostałe TCP"  
    else:
        return f"Inny ({proto})"
    
df_normal_clean = df_normal_all.copy()

df_normal_clean["proto_label"] = df_normal_clean.apply(classify_protocol, axis=1)

proto_counts = df_normal_clean["proto_label"].value_counts()
proto_percent = (proto_counts / proto_counts.sum() * 100).round(2)

print("=== Udział protokołów w ruchu normalnym ===")
for label, pct in proto_percent.items():
    print(f"{label:15s}: {pct:6.2f}% ({proto_counts[label]:,} flowów)")
print()


# Wykres udziału protokołów
plt.figure(figsize=(10, 6))
sns.barplot(
    x=proto_counts.index,
    y=proto_counts.values,
    palette=["#66c2a5", "#8da0cb", "#fc8d62", "#ffd92f"]
)

plt.title("Udział protokołów w ruchu normalnym")
plt.xlabel("Protokół")
plt.ylabel("Liczba przepływów")
plt.tight_layout()
plt.savefig("normal_protocol_distribution.png", dpi=300, bbox_inches="tight")
plt.show()
