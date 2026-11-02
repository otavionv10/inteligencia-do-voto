# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/progress.py
FUNCAO    : Progresso de tarefas longas em % (standalone), com ETA e
            watchdog anti-travamento. Para QUALQUER processo em background.
DEPENDE   : nenhum externo (stdlib). Imprime em stderr com \r (nao polui stdout).
USO       :
    from progress import Progress
    with Progress(total=n_linhas, label="build camada", every_pct=1.0) as p:
        for lote in lotes:
            ... processa lote ...
            p.tick(len(lote))          # anda N unidades
            p.message("ano 2022, ramo sq")  # status opcional
    # ao final: p.finish() (ou via with)
MODO WATCHDOG:
    Se nenhum tick ocorrer em `stall_s` (default 120s), imprime AVISO na mesma
    linha indicando "sem progresso ha XXs". Nao aborta a tarefa - so informa.
=============================================================================
"""
import sys
import time
import threading


class Progress:
    def __init__(self, total, label="", every_pct=1.0, stall_s=120,
                 watchdog=True, out=None):
        self.total = max(total, 1)
        self.label = label or "progresso"
        self.every_pct = max(every_pct, 0.1)
        self.stall_s = stall_s
        self.out = out or sys.stderr
        self.done = 0
        self.t0 = time.time()
        self.last_tick = self.t0
        self._last_pct = -100.0
        self._watch_dog = None
        self._stop = threading.Event()
        if watchdog:
            self._watch_dog = threading.Thread(target=self._watch, daemon=True)
            self._watch_dog.start()

    # -- controle -----------------------------------------------------------
    def tick(self, n=1):
        """Avança N unidades concluídas e re-renderiza se passar de 1%."""
        self.done = min(self.done + n, self.total)
        self.last_tick = time.time()
        pct = 100.0 * self.done / self.total
        if pct - self._last_pct >= self.every_pct or self.done >= self.total:
            self._render(pct)
            self._last_pct = pct

    def message(self, msg):
        """Status intermediário (mantém a percentagem visível na linha)."""
        pct = 100.0 * self.done / self.total
        self._render(pct, extra=msg)

    def finish(self):
        self._stop.set()
        if self._watch_dog is not None:
            self._watch_dog.join(timeout=1)
        self.tick(self.total - self.done)
        self.out.write("\n")

    # -- internos -----------------------------------------------------------
    def _render(self, pct, extra=None):
        el = time.time() - self.t0
        eta = el / max(pct / 100.0, 1e-9) - el if pct > 0 else 0
        w = 20
        filled = int(round(pct / 100.0 * w))
        bar = "#" * filled + "." * (w - filled)
        txt = (f"\r\x1b[2K[{self.label}] [{bar}] {pct:5.1f}% "
               f"({self._fmt(el)} decorrido, {self._fmt(eta)} restante)")
        if extra:
            txt += f"  | {extra}"
        self.out.write(txt)
        self.out.flush()

    @staticmethod
    def _fmt(s):
        s = int(s)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h:
            return f"{h:d}:{m:02d}:{sec:02d}"
        if m:
            return f"{m:d}:{sec:02d}"
        return f"{sec}s"

    def _watch(self):
        warned = False
        while not self._stop.wait(10):
            idle = time.time() - self.last_tick
            if idle > self.stall_s and not self._stop.is_set():
                if not warned:
                    self.out.write("\n")
                self.out.write(
                    f"\r\x1b[2K[AVISO] [{self.label}] sem progresso ha "
                    f"{self._fmt(idle)} (travado?)\r")
                self.out.flush()
                warned = True
            else:
                warned = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.finish()


def chunks_percent(total, n_chunks=100):
    """Parte `total` em ~N blocos de tamanhos iguais (útil para fatiar scans)."""
    if n_chunks <= 0:
        return [(0, total)]
    sz = max(total // n_chunks, 1)
    out = []
    start = 0
    while start < total:
        end = min(start + sz, total)
        out.append((start, end))
        start = end
    return out


def main():
    """Demo: gera progresso de 0->100%% em ~5s (teste visual)."""
    import time as _t
    n = 200
    with Progress(n, label="demo", every_pct=1.0, stall_s=60) as p:
        for _ in range(n):
            _t.sleep(0.025)
            p.tick(1)


if __name__ == "__main__":
    main()