# scripts/import_groups.py
import csv
from collections import defaultdict
from pathlib import Path

from app import create_app
from app.models import db, User, Student, Group, GroupStudent, GroupProfessor

# ===================== Config =====================
CSV_NAME = "import_grupos.csv"                         # CSV na mesma pasta do script
CSV_PATH = Path(__file__).resolve().parent / CSV_NAME  # caminho relativo ao script
DRY_RUN =  False #True                                         # <-- teste SEM gastar IDs (mude p/ False p/ importar)
AUTOCREATE_STUDENTS = False                            # criar "stub" de aluno se não existir?
DEFAULT_CAMPUS_ID = None                               # req. p/ AUTOCREATE
DEFAULT_OFFERING_ID = None                             # req. p/ AUTOCREATE
# ===================================================

def _norm(s: str) -> str:
    return " ".join((s or "").strip().split())

def detect_encoding_and_delimiter(pathlike):
    """Aceita str/Path; detecta encoding e delimitador (',' ';' ou '\\t')."""
    p = Path(pathlike)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {p.resolve()}")
    sample_bytes = p.read_bytes()[:8192]

    enc_used = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            sample = sample_bytes.decode(enc)
            enc_used = enc
            break
        except UnicodeDecodeError:
            continue
    if enc_used is None:
        sample = sample_bytes.decode("utf-8", errors="replace")
        enc_used = "utf-8"

    counts = {",": sample.count(","), ";": sample.count(";"), "\t": sample.count("\t")}
    delimiter = max(counts, key=counts.get) or ","
    return enc_used, delimiter

app = create_app()

with app.app_context():
    # 1) Ler CSV com detecção
    enc, delim = detect_encoding_and_delimiter(CSV_PATH)
    print(f"[INFO] Lendo: {CSV_PATH.resolve()} (encoding={enc}, delimiter='{delim}')")

    raw_rows = []
    with CSV_PATH.open("r", encoding=enc, newline="", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delim)
        # normaliza header para minúsculas
        lower_header = [h.lower() for h in reader.fieldnames or []]
        # mapeia nomes esperados -> nomes reais
        def key_of(expected):
            exp = expected.lower()
            for h in lower_header:
                if h == exp:
                    return h
            return expected  # deixa como está, se não achar
        k_orient = key_of("orientador")
        k_titulo = key_of("titulo")
        k_r1 = key_of("rgm_1")
        k_r2 = key_of("rgm_2")
        k_r3 = key_of("rgm_3")

        for row in reader:
            # torna as chaves case-insensitive
            lr = { (k.lower() if isinstance(k,str) else k): v for k,v in row.items() }
            raw_rows.append({
                "orientador": _norm(lr.get(k_orient, "")),
                "titulo": _norm(lr.get(k_titulo, "")),
                "rgms": [
                    _norm(lr.get(k_r1, "")),
                    _norm(lr.get(k_r2, "")),
                    _norm(lr.get(k_r3, "")),
                ],
            })

    # 2) Dedup por (titulo, rgm)
    seen_pair = set()            # (titulo, rgm)
    titles = set()
    orientadores = set()
    pairs_by_title = defaultdict(list)

    for r in raw_rows:
        if not r["titulo"]:
            continue
        titles.add(r["titulo"])
        if r["orientador"]:
            orientadores.add(r["orientador"])
        for rgm in r["rgms"]:
            if not rgm:
                continue
            key = (r["titulo"], rgm)
            if key in seen_pair:
                continue
            seen_pair.add(key)
            pairs_by_title[r["titulo"]].append((rgm, r["orientador"]))

    # 3) Pré-carregar entidades existentes
    users = {u.full_name: u for u in User.query.filter(User.full_name.in_(orientadores)).all()} if orientadores else {}
    groups = {g.title: g for g in Group.query.filter(Group.title.in_(titles)).all()} if titles else {}
    groups_by_id = {g.id: g.title for g in groups.values()}
    all_rgms = {rgm for title in pairs_by_title for (rgm, _) in pairs_by_title[title]}
    students = {s.rgm: s for s in Student.query.filter(Student.rgm.in_(all_rgms)).all()} if all_rgms else {}

    # 4) Criar grupos faltantes (sem gastar ID no DRY_RUN)
    created_groups = []
    if DRY_RUN:
        for title in titles:
            if title in groups:
                continue
            orient_name = next((orient for (rgm, orient) in pairs_by_title[title] if orient), None)
            print(f"[DRY] Criaria grupo: '{title}' (orientador={orient_name or '—'})")
            # simula existência para as próximas etapas
            class _Fake: pass
            g = _Fake()
            g.id = None
            g.title = title
            g.orientador_user_id = (users[orient_name].id if orient_name and orient_name in users else None)
            groups[title] = g
    else:
        for title in titles:
            if title in groups:
                continue
            orient_name = next((orient for (rgm, orient) in pairs_by_title[title] if orient), None)
            orient_user = users.get(orient_name) if orient_name else None
            g = Group(title=title, orientador_user_id=(orient_user.id if orient_user else None))
            db.session.add(g)
            db.session.flush()       # obtém ID (somente no modo real)
            groups[title] = g
            groups_by_id[g.id] = g.title
            created_groups.append(title)

    # 5) Vínculo ORIENTADOR em group_professors
    if DRY_RUN:
        for title in titles:
            g = groups[title]
            if getattr(g, "orientador_user_id", None):
                print(f"[DRY] Criaria vínculo ORIENTADOR: grupo='{title}' user_id={g.orientador_user_id}")
    else:
        existing_gp = set(db.session.query(GroupProfessor.group_id, GroupProfessor.user_id).all())
        new_gp = []
        for title in titles:
            g = groups[title]
            if g.orientador_user_id:
                key = (g.id, g.orientador_user_id)
                if key not in existing_gp:
                    new_gp.append(GroupProfessor(group_id=g.id, user_id=g.orientador_user_id, role_in_group="ORIENTADOR"))
                    existing_gp.add(key)
        if new_gp:
            db.session.add_all(new_gp)

    # 6) Vincular alunos aos grupos (respeita uq_student_single_group)
    #    - DRY_RUN somente relata, sem flush/commit (não gasta ID)
    existing_memberships = dict(db.session.query(GroupStudent.student_id, GroupStudent.group_id).all())
    pending_pairs = set()
    missing_students = set()
    conflicts = []
    duplicates = 0
    linked = 0

    def maybe_create_stub(rgm: str):
        if not AUTOCREATE_STUDENTS:
            return None
        if DEFAULT_CAMPUS_ID is None or DEFAULT_OFFERING_ID is None:
            return None
        st = Student(rgm=rgm, name=f"Aluno {rgm}", campus_id=DEFAULT_CAMPUS_ID, offering_id=DEFAULT_OFFERING_ID)
        if DRY_RUN:
            print(f"[DRY] Criaria Student stub para RGM {rgm} (campus={DEFAULT_CAMPUS_ID}, offering={DEFAULT_OFFERING_ID})")
            return None
        db.session.add(st)
        db.session.flush()
        students[rgm] = st
        return st

    for title, pairs in pairs_by_title.items():
        g = groups[title]
        for rgm, _orient in pairs:
            st = students.get(rgm) or maybe_create_stub(rgm)
            if not st:
                missing_students.add(rgm)
                continue

            gid = existing_memberships.get(st.id)
            if gid:
                # verifica se é o mesmo grupo (para grupos já existentes)
                same_group = (not DRY_RUN and gid == getattr(g, "id", None))
                if DRY_RUN and gid in groups_by_id and groups_by_id[gid] == title:
                    same_group = True

                if same_group:
                    duplicates += 1
                else:
                    conflicts.append((rgm, gid, getattr(g, "id", None), title))
                continue

            key = (getattr(g, "id", f"DRY:{title}"), st.id)
            if key in pending_pairs:
                duplicates += 1
                continue

            if DRY_RUN:
                print(f"[DRY] Vincularia RGM {rgm} ao grupo '{title}'")
            else:
                db.session.add(GroupStudent(group_id=g.id, student_id=st.id))
                existing_memberships[st.id] = g.id
                linked += 1
            pending_pairs.add(key)

    # 7) Finalização
    if DRY_RUN:
        db.session.rollback()
        print("[DRY-RUN] Sem commit. Nenhum ID consumido.")
    else:
        db.session.commit()

    # 8) Resumo
    print("\n=== Import Grupos ===")
    if created_groups:
        print(f"Criados {len(created_groups)} grupos:", ", ".join(created_groups))
    print(f"Vínculos criados: {linked}")
    print(f"Duplicatas puladas: {duplicates}")
    if missing_students:
        print(f"RGMs inexistentes em students: {', '.join(sorted(missing_students))}")
    if conflicts:
        print("Conflitos (RGM já vinculado a outro grupo):")
        for rgm, gid_old, gid_new, title in conflicts:
            # tenta resolver título antigo para facilitar leitura
            old_title = groups_by_id.get(gid_old, f"id={gid_old}")
            print(f" - RGM {rgm}: já está no grupo '{old_title}'; tentativa no grupo '{title}' pulada.")
