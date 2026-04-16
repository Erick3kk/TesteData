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

@app.route('/distribuir', methods=['POST'])
def distribuir_cashback():
    data = request.get_json()
    usuario_id = data.get('id')

    if not usuario_id:
        return jsonify({"status": "erro", "message": "ID não fornecido"}), 400

    conn = get_connection()
    if not conn:
        return jsonify({"erro": "Erro de conexão com o banco"}), 500
    
    try:
        cursor = conn.cursor()
        
        # Agora o PL/SQL recebe o ID como parâmetro (:user_id_param)
        plsql_block = """
        DECLARE
            CURSOR c_premiacao IS
                SELECT i.ID as inscricao_id, u.ID as user_id, i.VALOR_PAGO, i.TIPO
                FROM USUARIOS u
                JOIN INSCRICOES i ON u.ID = i.USUARIO_ID
                WHERE i.STATUS = 'PRESENT' AND u.ID = :user_id_param;
            
            v_total_presencas NUMBER;
            v_percentual NUMBER;
            v_cashback NUMBER;
            v_found BOOLEAN := FALSE;
        BEGIN
            FOR reg IN c_premiacao LOOP
                v_found := TRUE;
                SELECT COUNT(*) INTO v_total_presencas 
                FROM INSCRICOES 
                WHERE USUARIO_ID = reg.user_id AND STATUS = 'PRESENT';

                IF v_total_presencas > 3 THEN
                    v_percentual := 0.25;
                ELSIF reg.TIPO = 'VIP' THEN
                    v_percentual := 0.20;
                ELSE
                    v_percentual := 0.10;
                END IF;

                v_cashback := reg.VALOR_PAGO * v_percentual;

                UPDATE USUARIOS SET SALDO = SALDO + v_cashback WHERE ID = reg.user_id;
                
                INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA)
                VALUES (reg.inscricao_id, 'CASHBACK INDIVIDUAL ' || (v_percentual*100) || '%', SYSDATE);
            END LOOP;
            
            COMMIT;
        END;
        """
        
        cursor.execute(plsql_block, user_id_param=usuario_id)
        return jsonify({"status": "sucesso", "message": f"Cashback processado para o ID {usuario_id}!"})
    
    except Exception as e:
        return jsonify({"status": "erro", "message": str(e)}), 500
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