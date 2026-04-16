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
        print(f"Erro de Conexão: {e}")
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
        usuarios = [{"id": r[0], "nome": r[1], "saldo": f"{r[2]:.2f}"} for r in cursor.fetchall()]
        return jsonify(usuarios)
    finally: conn.close()

@app.route("/distribuir", methods=["POST"])
def distribuir_cashback():
    data = request.get_json()
    if not data or 'id_evento' not in data:
        return jsonify({"status": "erro", "message": "ID não enviado"}), 400
    
    id_alvo = data.get('id_evento')
    conn = get_connection()
    if not conn: return jsonify({"status": "erro", "message": "Falha no Banco"}), 500
    
    try:
        cursor = conn.cursor()
        # PL/SQL corrigido para processar apenas o ID do input
        plsql_block = """
        DECLARE
            v_taxa NUMBER;
            v_total NUMBER := 0;
        BEGIN
            FOR reg IN (SELECT ID, USUARIO_ID, VALOR_PAGO, TIPO 
                        FROM INSCRICOES WHERE ID = :id AND STATUS = 'PRESENT') LOOP
                
                IF (SELECT COUNT(*) FROM INSCRICOES WHERE USUARIO_ID = reg.USUARIO_ID AND STATUS = 'PRESENT') > 3 THEN
                    v_taxa := 0.25;
                ELSIF reg.TIPO = 'VIP' THEN
                    v_taxa := 0.20;
                ELSE
                    v_taxa := 0.10;
                END IF;

                UPDATE USUARIOS SET SALDO = SALDO + (reg.VALOR_PAGO * v_taxa) WHERE ID = reg.USUARIO_ID;
                
                INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA)
                VALUES (reg.ID, 'CASHBACK APLICADO ID ' || reg.ID, SYSDATE);
                v_total := v_total + 1;
            END LOOP;
            COMMIT;
            :saida := v_total;
        END;
        """
        v_saida = cursor.var(oracledb.NUMBER)
        cursor.execute(plsql_block, id=id_alvo, saida=v_saida)
        
        if v_saida.getvalue() == 0:
            return jsonify({"status": "erro", "message": f"ID {id_alvo} não encontrado ou ausente."})
            
        return jsonify({"status": "sucesso", "message": f"Cashback aplicado ao ID {id_alvo}!"})
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
        return jsonify({"status": "sucesso", "message": "Saldos resetados para R$ 100,00!"})
    finally: conn.close()

if __name__ == "__main__":
    app.run(debug=True)