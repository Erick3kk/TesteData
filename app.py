import oracledb
import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def get_connection():
    try:
        return oracledb.connect(
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            dsn=os.environ.get("DB_DSN"),
        )
    except oracledb.DatabaseError as e:
        (error,) = e.args
        print(f"[DATABASE ERROR] {error.message}")
        return None

def connection_error():
    return jsonify({"status": "erro", "message": "Conexão com o Nexus Core falhou."}), 500

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    conn = get_connection()
    if not conn: return connection_error()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.ID, u.NOME, u.SALDO,
                (SELECT TIPO FROM INSCRICOES WHERE USUARIO_ID = u.ID AND ROWNUM = 1) AS CATEGORIA,
                (SELECT COUNT(*) FROM INSCRICOES WHERE USUARIO_ID = u.ID AND STATUS = 'PRESENT') AS TOTAL_PRES
            FROM USUARIOS u ORDER BY u.ID
        """)
        usuarios = [
            {
                "id": row[0],
                "nome": row[1],
                "saldo": f"{row[2]:.2f}",
                "tipo": row[3] if row[3] else "REGULAR",
                "presencas": row[4],
            }
            for row in cursor.fetchall()
        ]
        return jsonify(usuarios)
    finally:
        conn.close()

@app.route("/logs", methods=["GET"])
def listar_logs():
    conn = get_connection()
    if not conn: return connection_error()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.ID, u.NOME, l.MOTIVO, TO_CHAR(l.DATA, 'DD/MM HH24:MI')
            FROM LOG_AUDITORIA l
            JOIN INSCRICOES i ON l.INSCRICAO_ID = i.ID
            JOIN USUARIOS u ON i.USUARIO_ID = u.ID
            ORDER BY l.DATA DESC FETCH FIRST 50 ROWS ONLY
        """)
        logs = [{"id": r[0], "participante": r[1], "motivo": r[2], "data": r[3]} for r in cursor.fetchall()]
        return jsonify(logs)
    finally:
        conn.close()

@app.route("/distribuir", methods=["POST"])
def distribuir_cashback():
    conn = get_connection()
    if not conn: return connection_error()
    try:
        cursor = conn.cursor()
        # O bloco abaixo agora segue: 25% (>3 presenças), 20% (VIP), 10% (Resto)
        plsql_block = """
        DECLARE
            v_taxa NUMBER;
            v_valor_final NUMBER;
            v_presencas NUMBER;
        BEGIN
            FOR reg IN (SELECT i.ID, i.USUARIO_ID, i.VALOR_PAGO, i.TIPO FROM INSCRICOES i WHERE i.STATUS = 'PRESENT') LOOP
                
                SELECT COUNT(*) INTO v_presencas FROM INSCRICOES 
                WHERE USUARIO_ID = reg.USUARIO_ID AND STATUS = 'PRESENT';

                IF v_presencas > 3 THEN 
                    v_taxa := 0.25;
                ELSIF reg.TIPO = 'VIP' THEN 
                    v_taxa := 0.20;
                ELSE 
                    v_taxa := 0.10; 
                END IF;

                v_valor_final := reg.VALOR_PAGO * v_taxa;

                UPDATE USUARIOS SET SALDO = SALDO + v_valor_final WHERE ID = reg.USUARIO_ID;

                INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA)
                VALUES (reg.ID, 'CRÉDITO ECO (' || (v_taxa*100) || '%) | VALOR: R$ ' || TO_CHAR(v_valor_final, 'FM999G990D00'), SYSDATE);
            END LOOP;
            COMMIT;
        END;
        """
        cursor.execute(plsql_block)
        return jsonify({"status": "sucesso", "message": "Créditos distribuídos com sucesso!"})
    finally:
        conn.close()

@app.route("/reset", methods=["POST"])
def resetar_dados():
    conn = get_connection()
    if not conn: return connection_error()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM LOG_AUDITORIA")
        cursor.execute("UPDATE USUARIOS SET SALDO = 0")
        conn.commit()
        return jsonify({"status": "sucesso", "message": "Sistema limpo com sucesso."})
    finally:
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)