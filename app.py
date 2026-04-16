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
        res = [{"id": r[0], "nome": r[1], "saldo": f"{r[2]:.2f}"} for r in cursor.fetchall()]
        return jsonify(res)
    finally: conn.close()

@app.route("/distribuir", methods=["POST"])
def distribuir_cashback():
    data = request.get_json()
    try:
        id_alvo = int(data.get('id_evento'))
    except:
        return jsonify({"status": "erro", "message": "ID Inválido"}), 400

    conn = get_connection()
    if not conn: return jsonify({"status": "erro", "message": "Erro de conexão"}), 500
    
    try:
        cursor = conn.cursor()
        
        # 1. Busca os dados da inscrição específica
        cursor.execute("""
            SELECT USUARIO_ID, VALOR_PAGO, TIPO 
            FROM INSCRICOES 
            WHERE ID = :1 AND STATUS = 'PRESENT'
        """, [id_alvo])
        
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"status": "erro", "message": f"ID {id_alvo} não encontrado ou não está 'PRESENT'."})

        usuario_id, valor_pago, tipo = row

        # 2. Conta presenças para o cálculo da taxa
        cursor.execute("SELECT COUNT(*) FROM INSCRICOES WHERE USUARIO_ID = :1 AND STATUS = 'PRESENT'", [usuario_id])
        presencas = cursor.fetchone()[0]

        # 3. Define a taxa
        if presencas > 3:
            taxa = 0.25
        elif tipo == 'VIP':
            taxa = 0.20
        else:
            taxa = 0.10

        valor_cashback = valor_pago * taxa

        # 4. Atualiza o saldo do usuário
        cursor.execute("UPDATE USUARIOS SET SALDO = SALDO + :1 WHERE ID = :2", [valor_cashback, usuario_id])
        
        # 5. Registra o Log
        cursor.execute("""
            INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA) 
            VALUES (:1, :2, SYSDATE)
        """, [id_alvo, f"CASHBACK INDIVIDUAL {int(taxa*100)}%"])

        conn.commit()
        return jsonify({"status": "sucesso", "message": f"Sucesso! R$ {valor_cashback:.2f} creditados."})

    except Exception as e:
        # Se der erro, o Python vai nos dizer exatamente o que o Oracle respondeu
        print(f"ERRO DE BANCO: {str(e)}")
        return jsonify({"status": "erro", "message": f"Erro no Oracle: {str(e)}"}), 500
    finally:
        conn.close()

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

if __name__ == "__main__":
    app.run(debug=True)