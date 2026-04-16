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
        print(f"Erro Conexao: {e}")
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
    # Garante que o ID seja um inteiro puro do Python
    try:
        id_alvo = int(data.get('id_evento'))
    except (ValueError, TypeError):
        return jsonify({"status": "erro", "message": "ID Inválido"}), 400

    conn = get_connection()
    if not conn: return jsonify({"status": "erro", "message": "Erro de Conexão"}), 500
    
    try:
        cursor = conn.cursor()
        # Query simplificada para evitar erro de tipo no Oracle
        plsql = """
        DECLARE
            v_taxa NUMBER;
        BEGIN
            FOR reg IN (SELECT ID, USUARIO_ID, VALOR_PAGO, TIPO 
                        FROM INSCRICOES WHERE ID = :1 AND STATUS = 'PRESENT') LOOP
                
                IF (SELECT COUNT(*) FROM INSCRICOES WHERE USUARIO_ID = reg.USUARIO_ID AND STATUS = 'PRESENT') > 3 THEN
                    v_taxa := 0.25;
                ELSIF reg.TIPO = 'VIP' THEN
                    v_taxa := 0.20;
                ELSE
                    v_taxa := 0.10;
                END IF;

                UPDATE USUARIOS SET SALDO = SALDO + (reg.VALOR_PAGO * v_taxa) WHERE ID = reg.USUARIO_ID;
                
                INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA)
                VALUES (reg.ID, 'CASHBACK INDIVIDUAL OK', SYSDATE);
            END LOOP;
            COMMIT;
        END;
        """
        cursor.execute(plsql, [id_alvo])
        return jsonify({"status": "sucesso", "message": f"ID {id_alvo} processado!"})
    except Exception as e:
        return jsonify({"status": "erro", "message": str(e)}), 500
    finally: conn.close()

@app.route("/reset", methods=["POST"])
def resetar_dados():
    conn = get_connection()
    if not conn: return jsonify({"status": "erro"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE USUARIOS SET SALDO = 100")
        cursor.execute("DELETE FROM LOG_AUDITORIA")
        conn.commit()
        return jsonify({"status": "sucesso", "message": "Resetado para R$ 100,00!"})
    finally: conn.close()