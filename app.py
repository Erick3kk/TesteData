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
    except Exception as e:
        print(f"[ERRO] {e}")
        return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    conn = get_connection()
    if not conn: return jsonify([]), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT ID, NOME, SALDO FROM USUARIOS ORDER BY ID")
        return jsonify([{"id": r[0], "nome": r[1], "saldo": f"{r[2]:.2f}"} for r in cursor.fetchall()])
    finally: conn.close()

@app.route("/distribuir", methods=["POST"])
def distribuir_cashback():
    data = request.get_json()
    id_evento = data.get('id_evento') # Captura o ID do campo de auditoria

    conn = get_connection()
    if not conn: return connection_error()

    try:
        cursor = conn.cursor()
        # PL/SQL agora filtra especificamente pela INSCRICAO_ID informada
        plsql_block = """
        DECLARE
            v_percentual NUMBER;
            v_cashback   NUMBER;
        BEGIN
            FOR reg IN (SELECT ID, USUARIO_ID, VALOR_PAGO, TIPO 
                        FROM INSCRICOES 
                        WHERE ID = :id_evt AND STATUS = 'PRESENT') LOOP
                
                -- Lógica de escalonamento conforme solicitado
                IF (SELECT COUNT(*) FROM INSCRICOES WHERE USUARIO_ID = reg.USUARIO_ID AND STATUS = 'PRESENT') > 3 THEN
                    v_percentual := 0.25;
                ELSIF reg.TIPO = 'VIP' THEN
                    v_percentual := 0.20;
                ELSE
                    v_percentual := 0.10;
                END IF;

                v_cashback := reg.VALOR_PAGO * v_percentual;

                UPDATE USUARIOS SET SALDO = SALDO + v_cashback WHERE ID = reg.USUARIO_ID;

                INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA)
                VALUES (reg.ID, 'CASHBACK INDIVIDUAL ' || (v_percentual*100) || '%', SYSDATE);
            END LOOP;
            COMMIT;
        END;
        """
        cursor.execute(plsql_block, [id_evento])
        return jsonify({"status": "sucesso", "message": f"Cashback aplicado para o evento #{id_evento}!"})
    finally:
        conn.close()

@app.route("/reset", methods=["POST"])
def resetar_dados():
    conn = get_connection()
    if not conn: return connection_error()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM LOG_AUDITORIA")
        cursor.execute("UPDATE USUARIOS SET SALDO = 100") # Agora reseta para 100
        conn.commit()
        return jsonify({"status": "sucesso", "message": "Saldos resetados para R$ 100,00!"})
    finally:
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)