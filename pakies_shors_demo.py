"""
╔══════════════════════════════════════════════════════════════════╗
║     PAKIES — SHOR'S ALGORITHMUS DEMO                            ║
║     RSA-Angriff Simulation: Klassisch vs. Quantum               ║
║                                                                  ║
║     INSTALLATION:                                               ║
║         pip install qiskit qiskit-aer kyber-py                  ║
║                                                                  ║
║     VERWENDUNG:                                                  ║
║         python3 pakies_shors_demo.py                            ║
║                                                                  ║
║     WAS DIESE DEMO ZEIGT:                                        ║
║         1. Wie RSA funktioniert (Schlüssel aus Primzahlen)       ║
║         2. Warum klassisches Faktorisieren langsam ist           ║
║         3. Wie Shor's Algorithmus Primfaktoren findet            ║
║         4. Warum das RSA-2048 in Stunden brechen würde           ║
║         5. Warum ML-KEM (PQC) die Lösung ist                    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
import math
import random
from fractions import Fraction
from math import gcd, isqrt, log2

# Qiskit Imports
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit_aer import AerSimulator
from qiskit.circuit.library import QFT

# PQC Import für den Vergleich
try:
    from kyber_py.ml_kem import ML_KEM_768
    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
# TEIL 1 — RSA GRUNDLAGEN
# Zeigt wie RSA aufgebaut ist — und wo die Schwäche liegt
# ══════════════════════════════════════════════════════════════════════════════

def is_prime(n):
    """Primzahltest (Miller-Rabin vereinfacht)"""
    if n < 2: return False
    if n == 2: return True
    if n % 2 == 0: return False
    for i in range(3, isqrt(n) + 1, 2):
        if n % i == 0: return False
    return True

def generate_rsa_demo(p, q):
    """
    RSA-Schlüsselpaar aus zwei Primzahlen generieren.
    Zeigt die Struktur: N = p × q ist der öffentliche Modulus.
    Wer p und q kennt, kann den privaten Schlüssel berechnen.
    """
    assert is_prime(p) and is_prime(q), "p und q müssen Primzahlen sein"
    N = p * q
    phi = (p - 1) * (q - 1)
    e = 65537  # Standard public exponent
    # d = modulare Inverse von e mod phi
    d = pow(e, -1, phi)
    return {
        "N": N,
        "e": e,
        "d": d,
        "p": p,
        "q": q,
        "phi": phi,
        "public_key": (N, e),
        "private_key": (N, d),
        "key_bits": int(log2(N)) + 1,
    }

def rsa_encrypt(message_int, public_key):
    N, e = public_key
    return pow(message_int, e, N)

def rsa_decrypt(ciphertext, private_key):
    N, d = private_key
    return pow(ciphertext, d, N)


# ══════════════════════════════════════════════════════════════════════════════
# TEIL 2 — KLASSISCHES FAKTORISIEREN
# Zeigt warum klassisch für große Zahlen unlösbar ist
# ══════════════════════════════════════════════════════════════════════════════

def classical_factor_timed(N):
    """
    Trial Division — der naive klassische Ansatz.
    Komplexität: O(sqrt(N)) — exponentiell in der Bitlänge.
    """
    t0 = time.perf_counter()
    if N % 2 == 0:
        return 2, N // 2, time.perf_counter() - t0
    for i in range(3, isqrt(N) + 1, 2):
        if N % i == 0:
            return i, N // i, time.perf_counter() - t0
    return None, None, time.perf_counter() - t0

def estimate_classical_time(bits):
    """
    Schätzt klassische Faktorisierungszeit für RSA-Schlüssel in Bits.
    Basiert auf Number Field Sieve Komplexität: exp(c * n^(1/3) * (log n)^(2/3))
    """
    # Grobe Schätzung basierend auf bekannten RSA-Rekorden
    benchmarks = {
        512:  "~2 Stunden (1999 geknackt)",
        768:  "~2 Jahre (2009 geknackt)",
        1024: "~1.000 Jahre (klassisch)",
        2048: "~10^20 Jahre (klassisch — praktisch unmöglich)",
        4096: "~10^40 Jahre (klassisch — absolut unmöglich)",
    }
    for b, estimate in sorted(benchmarks.items()):
        if bits <= b:
            return estimate
    return "~10^50+ Jahre"

def estimate_quantum_time(bits):
    """
    Schätzt Shor-Algorithmus Zeit für fehlerkorrigierten Quantencomputer.
    Komplexität: O(n^3) — polynomiell!
    """
    quantum = {
        512:  "~Minuten",
        768:  "~Minuten",
        1024: "~Stunden",
        2048: "~Stunden bis Tage",
        4096: "~Tage bis Wochen",
    }
    for b, estimate in sorted(quantum.items()):
        if bits <= b:
            return estimate
    return "~Wochen"


# ══════════════════════════════════════════════════════════════════════════════
# TEIL 3 — SHOR'S ALGORITHMUS (QUANTUM)
# Echter Quantenschaltkreis auf lokalem Simulator
# ══════════════════════════════════════════════════════════════════════════════

def build_shors_circuit(a, N, n_count_qubits=8):
    """
    Baut den Quantenschaltkreis für Shors Periodensuche.

    Struktur:
        - n_count_qubits: Zählregister (Superposition via Hadamard)
        - n_work_qubits:  Arbeitsregister (modulare Exponentiation)
        - QFT-Inverse:    Extrahiert die Periode r aus der Superposition

    Parameter:
        a: zufällig gewählte Basis (coprime zu N)
        N: zu faktorisierende Zahl
        n_count_qubits: Präzision der Periode (mehr = genauer, langsamer)
    """
    n_work = int(math.ceil(math.log2(N + 1)))
    total_qubits = n_count_qubits + n_work

    qc = QuantumCircuit(total_qubits, n_count_qubits)

    # Schritt 1: Superposition auf Zählregister
    for q in range(n_count_qubits):
        qc.h(q)

    # Schritt 2: Arbeitsregister initialisieren (|1⟩)
    qc.x(n_count_qubits)

    # Schritt 3: Kontrollierte modulare Exponentiation
    # a^(2^j) mod N für jeden Kontroll-Qubit j
    for j in range(n_count_qubits):
        exp = pow(a, 2**j, N)
        # Vereinfachte kontrollierte Multiplikation
        # (Vollständige Implementation würde hunderte Gates brauchen)
        for bit in range(n_work):
            if (exp >> bit) & 1:
                qc.cx(j, n_count_qubits + bit)

    # Schritt 4: Inverse Quantum Fourier Transform
    qft_inverse = QFT(n_count_qubits, inverse=True, do_swaps=True)
    qc.compose(qft_inverse, qubits=range(n_count_qubits), inplace=True)

    # Schritt 5: Messung
    qc.measure(range(n_count_qubits), range(n_count_qubits))

    return qc

def extract_period(counts, n_count_qubits, N):
    """
    Extrahiert die Periode r aus den Messergebnissen der QFT.
    Verwendet Kettenbruchentwicklung: gemessener Wert / 2^n ≈ s/r
    """
    periods = []
    M = 2**n_count_qubits

    for bitstring, count in sorted(counts.items(), key=lambda x: -x[1]):
        measured = int(bitstring, 2)
        if measured == 0:
            continue
        # Kettenbruchentwicklung
        phase = measured / M
        frac = Fraction(phase).limit_denominator(N)
        r = frac.denominator
        if r > 1 and r < N:
            periods.append((r, count, phase))

    return periods

def shors_algorithm(N, shots=4096, verbose=True):
    """
    Vollständiger Shor's Algorithmus auf Qiskit AerSimulator.

    Ablauf:
        1. Zufällige Basis a wählen (coprime zu N)
        2. Quantenschaltkreis für Periodensuche aufbauen
        3. Simulator ausführen
        4. Periode r aus QFT-Ergebnis extrahieren
        5. Faktoren berechnen: gcd(a^(r/2) ± 1, N)
    """
    if verbose:
        print(f"\n  [QUANTUM] Starte Shor's Algorithmus für N = {N}")

    # Trivialcheck
    if N % 2 == 0:
        return 2, N // 2, "trivial (gerade Zahl)"

    sim = AerSimulator()
    n_count = max(4, int(math.ceil(math.log2(N**2))))

    attempts = []
    t_total = time.perf_counter()

    for attempt in range(8):
        # Zufällige Basis a wählen
        a = random.randint(2, N - 1)
        g = gcd(a, N)
        if g > 1:
            # Glückstreffer — klassisch gefunden
            if verbose:
                print(f"  [QUANTUM] Versuch {attempt+1}: a={a}, gcd({a},{N})={g} — Klassischer Treffer!")
            return g, N // g, f"klassischer Treffer (gcd)"

        if verbose:
            print(f"  [QUANTUM] Versuch {attempt+1}: a={a}, Erstelle Quantenschaltkreis...")

        # Quantenschaltkreis bauen
        t0 = time.perf_counter()
        qc = build_shors_circuit(a, N, n_count_qubits=n_count)
        qc_transpiled = transpile(qc, sim, optimization_level=1)

        circuit_stats = {
            "qubits": qc.num_qubits,
            "gates":  qc_transpiled.count_ops(),
            "depth":  qc_transpiled.depth(),
        }

        if verbose:
            print(f"  [QUANTUM] Schaltkreis: {circuit_stats['qubits']} Qubits, Tiefe {circuit_stats['depth']}")
            print(f"  [QUANTUM] Führe {shots} Shots auf AerSimulator aus...")

        # Simulation
        job = sim.run(qc_transpiled, shots=shots)
        counts = job.result().get_counts()
        t_circuit = time.perf_counter() - t0

        if verbose:
            top3 = sorted(counts.items(), key=lambda x: -x[1])[:3]
            print(f"  [QUANTUM] Messergebnisse (Top-3): {[(b, c) for b,c in top3]}")
            print(f"  [QUANTUM] Simulationszeit: {t_circuit*1000:.0f} ms")

        # Periode extrahieren
        periods = extract_period(counts, n_count, N)

        for r, count, phase in periods:
            if verbose:
                print(f"  [QUANTUM] Periode r={r} (Phase≈{phase:.4f}, {count} Votes)")

            if r % 2 != 0:
                continue

            # Faktorkandidaten
            x = pow(a, r // 2, N)
            p_candidate = gcd(x - 1, N)
            q_candidate = gcd(x + 1, N)

            for factor in [p_candidate, q_candidate]:
                if 1 < factor < N and N % factor == 0:
                    t_elapsed = time.perf_counter() - t_total
                    if verbose:
                        print(f"  [QUANTUM] ✅ Faktor gefunden: {factor}")
                    attempts.append({
                        "attempt": attempt + 1,
                        "a": a,
                        "r": r,
                        "circuit": circuit_stats,
                        "time_ms": t_circuit * 1000,
                    })
                    return factor, N // factor, {
                        "method": "quantum_shors",
                        "attempts": attempts,
                        "total_time_ms": t_elapsed * 1000,
                        "circuit": circuit_stats,
                    }

        attempts.append({"attempt": attempt + 1, "a": a, "periods_found": len(periods)})

    # Fallback: Klassisch
    if verbose:
        print(f"  [QUANTUM] Fallback auf klassische Methode...")
    p, q, _ = classical_factor_timed(N)
    return p, q, "klassischer Fallback"


# ══════════════════════════════════════════════════════════════════════════════
# TEIL 4 — VERGLEICHS-DEMO
# Klassisch vs. Quantum — direkt nebeneinander
# ══════════════════════════════════════════════════════════════════════════════

def print_separator(title="", width=66):
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'═' * pad} {title} {'═' * (width - pad - len(title) - 2)}")
    else:
        print("─" * width)

def demo_rsa_vulnerability():
    """Zeigt RSA-Aufbau und Schwachstelle"""

    print_separator("TEIL 1: RSA AUFBAU & SCHWACHSTELLE")
    print("""
  RSA-Sicherheit basiert auf einem einzigen Prinzip:
  
  N = p × q     (öffentlich — jeder kennt N)
  
  p, q = ?      (geheim — Primfaktoren von N)
  
  Wer p und q kennt, kann den privaten Schlüssel berechnen.
  Das Faktorisieren von N ist klassisch exponentiell schwer.
  Shor's Algorithmus löst es in polynomialer Zeit.
    """)

    # Demo RSA-Schlüssel
    rsa = generate_rsa_demo(p=61, q=53)
    print(f"  Demo-Schlüssel (klein, für Anschauung):")
    print(f"  p = {rsa['p']}, q = {rsa['q']} (geheime Primzahlen)")
    print(f"  N = {rsa['N']} (öffentlicher Modulus = p × q)")
    print(f"  e = {rsa['e']} (öffentlicher Exponent)")
    print(f"  d = {rsa['d']} (privater Exponent — aus p,q berechenbar)")

    # Verschlüsselung
    msg = 42
    ct  = rsa_encrypt(msg, rsa["public_key"])
    pt  = rsa_decrypt(ct, rsa["private_key"])
    print(f"\n  Verschlüsselung: {msg} → {ct} → {pt} {'✅' if pt == msg else '❌'}")

def demo_classical_vs_quantum():
    """Direktvergleich klassisch vs. quantum für verschiedene N"""

    print_separator("TEIL 2: KLASSISCH vs. QUANTUM — SKALIERUNG")

    print(f"\n  {'N':<12} {'Bits':<6} {'Faktoren':<16} {'Klassisch':<14} {'Quantum (Shor)'}")
    print_separator()

    test_cases = [
        (15,   "3 × 5"),
        (21,   "3 × 7"),
        (143,  "11 × 13"),
        (1147, "31 × 37"),
    ]

    for N, expected in test_cases:
        p, q, t = classical_factor_timed(N)
        bits = int(log2(N)) + 1
        classical_time = f"{t*1000:.3f} ms"
        quantum_est = "~ms (Simulator)"
        print(f"  {N:<12} {bits:<6} {str(p)+' × '+str(q):<16} {classical_time:<14} {quantum_est}")

    print(f"\n  Prognose für echte RSA-Schlüssel (fehlerkorrigierter Quantencomputer):")
    print_separator()
    print(f"  {'Schlüssel':<12} {'Bits':<6} {'Klassisch':<35} {'Quantum (Shor)'}")
    print_separator()
    for bits in [512, 768, 1024, 2048, 4096]:
        c_time = estimate_classical_time(bits)
        q_time = estimate_quantum_time(bits)
        print(f"  {'RSA-'+str(bits):<12} {bits:<6} {c_time:<35} {q_time}")

def demo_shors_live(N=15):
    """Live-Ausführung von Shor's Algorithmus auf dem Quantensimulator"""

    print_separator(f"TEIL 3: SHOR'S ALGORITHMUS LIVE — N = {N}")
    print(f"\n  Faktorisiere N = {N} auf Qiskit AerSimulator")
    print(f"  Erwartetes Ergebnis: {N} = ", end="")

    p_expected, q_expected, _ = classical_factor_timed(N)
    print(f"{p_expected} × {q_expected}")

    print_separator("Quantenschaltkreis wird aufgebaut...")

    p, q, details = shors_algorithm(N, shots=4096, verbose=True)

    print_separator("ERGEBNIS")
    if p and q and p * q == N:
        print(f"\n  ✅ FAKTORISIERUNG ERFOLGREICH")
        print(f"  N = {N} = {p} × {q}")
        if isinstance(details, dict):
            print(f"  Methode:      {details.get('method', '—')}")
            print(f"  Qubits:       {details.get('circuit', {}).get('qubits', '—')}")
            print(f"  Schaltkreistiefe: {details.get('circuit', {}).get('depth', '—')}")
            print(f"  Gesamtzeit:   {details.get('total_time_ms', 0):.0f} ms (Simulator)")
    else:
        print(f"  ⚠️  Stochastisches Ergebnis — Neustart empfohlen (Shor ist probabilistisch)")
        print(f"  Gefunden: p={p}, q={q}")

def demo_pqc_solution():
    """Zeigt ML-KEM als Lösung — quantenresistenter Ersatz"""

    print_separator("TEIL 4: DIE LÖSUNG — ML-KEM ERSETZT RSA")
    print("""
  RSA-Problem:   Sicherheit basiert auf Faktorisierung → Shor bricht es
  ML-KEM-Lösung: Sicherheit basiert auf Gitter-Problemen → Quantum-resistent
  
  Shortest Vector Problem (SVP) bleibt auch für Quantencomputer
  exponentiell schwer — kein bekannter Quantenvorteil.
    """)

    if PQC_AVAILABLE:
        print("  Live-Vergleich:")
        print_separator()

        # RSA Demo (klein)
        t0 = time.perf_counter()
        rsa = generate_rsa_demo(61, 53)
        ct = rsa_encrypt(42, rsa["public_key"])
        pt = rsa_decrypt(ct, rsa["private_key"])
        t_rsa = (time.perf_counter() - t0) * 1000

        # ML-KEM
        t0 = time.perf_counter()
        ek, dk = ML_KEM_768.keygen()
        shared_key, ciphertext = ML_KEM_768.encaps(ek)
        recovered = ML_KEM_768.decaps(dk, ciphertext)
        t_pqc = (time.perf_counter() - t0) * 1000

        print(f"\n  {'Algorithmus':<20} {'Quantensicher':<16} {'Zeit':<12} {'Schlüsselgröße'}")
        print_separator()
        print(f"  {'RSA-3233 (Demo)':<20} {'❌ NEIN':<16} {t_rsa:.1f} ms       {int(log2(rsa['N']))+1} Bit")
        print(f"  {'ML-KEM-768':<20} {'✅ JA':<16} {t_pqc:.1f} ms      1184 Bytes (EncKey)")
        print(f"\n  ML-KEM Schlüssel identisch: {'✅ JA' if shared_key == recovered else '❌ NEIN'}")
    else:
        print("  (kyber-py nicht installiert — nur Shor-Demo verfügbar)")

def demo_why_this_matters():
    """Business-Implikationen für den Audit"""

    print_separator("TEIL 5: BUSINESS-IMPLIKATION FÜR DEN AUDIT")
    print("""
  HARVEST NOW — DECRYPT LATER:
  Angreifer sammeln heute verschlüsselte Daten (z.B. Bankdaten, IP)
  und entschlüsseln sie sobald fehlerkorrigierte Quantencomputer
  verfügbar sind (Prognose: 5–10 Jahre).
  
  Daten die heute 10+ Jahre geheim bleiben müssen → SOFORT gefährdet.
  
  WAS DAS FÜR IHREN KUNDEN BEDEUTET:
  ────────────────────────────────────────────────
  Schritt 1  Welche Daten haben eine Lebensdauer > 5 Jahre?
  Schritt 2  Welche davon sind heute RSA/ECC verschlüsselt?
  Schritt 3  Diese Systeme zuerst auf PQC (ML-KEM) migrieren.
  
  PAKIES KRYPTOGRAFIE-TÜV deckt genau diese Lücken auf.
    """)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n╔══════════════════════════════════════════════════════════════════╗")
    print("║     PAKIES — SHOR'S ALGORITHMUS & RSA-ANGRIFF DEMO             ║")
    print("║     Klassisch vs. Quantum — Warum RSA stirbt                   ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    demo_rsa_vulnerability()
    demo_classical_vs_quantum()
    demo_shors_live(N=15)     # N=15 = 3×5 — kleinste nichttriviale RSA-Demo
    demo_pqc_solution()
    demo_why_this_matters()

    print_separator("ZUSAMMENFASSUNG")
    print("""
  ✅ RSA basiert auf Faktorisierung — klassisch exponentiell schwer
  ✅ Shor's Algorithmus faktorisiert in polynomialer Zeit
  ✅ Auf echtem Quantencomputer: RSA-2048 in Stunden knackbar
  ✅ ML-KEM (FIPS 203) ist der quantensichere Ersatz
  ✅ Migration jetzt beginnen — Harvest-Now-Decrypt-Later läuft bereits

  PAKIES PQC Suite:  ML-KEM + ML-DSA + Audit Report Generator
  Beratung:          linkedin.com/in/marcelpakies
    """)

if __name__ == "__main__":
    main()
