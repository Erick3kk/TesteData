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
        print(f"Erro: {e}")
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
    id_alvo = data.get('id_evento')
    conn = get_connection()
    if not conn: return jsonify({"status": "erro", "message": "Sem conexão"}), 500
    try:
        cursor = conn.cursor()
        # Busca dados da inscrição
        cursor.execute("SELECT USUARIO_ID, VALOR_PAGO, TIPO FROM INSCRICOES WHERE ID = :1 AND STATUS = 'PRESENT'", [id_alvo])
        row = cursor.fetchone()
        if not row:
            return jsonify({"status": "erro", "message": "ID não encontrado ou ausente"}), 404
        
        u_id, valor, tipo = row
        cursor.execute("SELECT COUNT(*) FROM INSCRICOES WHERE USUARIO_ID = :1 AND STATUS = 'PRESENT'", [u_id])
        presencas = cursor.fetchone()[0]
        
        taxa = 0.25 if presencas > 3 else (0.20 if tipo == 'VIP' else 0.10)
        ganho = valor * taxa

        cursor.execute("UPDATE USUARIOS SET SALDO = SALDO + :1 WHERE ID = :2", [ganho, u_id])
        cursor.execute("INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA) VALUES (:1, 'CASHBACK', SYSDATE)", [id_alvo])
        conn.commit()
        return jsonify({"status": "sucesso", "message": f"Creditado R$ {ganho:.2f}!"})
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
        return jsonify({"status": "sucesso", "message": "Saldos resetados para R$ 100!"})
    finally: conn.close()