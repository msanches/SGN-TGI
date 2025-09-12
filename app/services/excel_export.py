from openpyxl import Workbook
from flask import make_response
from datetime import datetime

COLUMNS = [
    "Nº Grupo","Título","RGM","Nome","Campus","Oferta","Orientador",
    "Relatório I","Relatório II","Paper","Apres. Banner"
]


def export_demo():
    wb = Workbook()
    ws = wb.active
    ws.title = "TGI"
    ws.append(COLUMNS)
    ws.append([1,"Sistema TGI","0001","Maria","São Paulo","2025.1","Prof. Ana",8.5,9.0,9.5,9.2])
    ws.append([2,"Projeto X","0002","João","Rio de Janeiro","2025.1","Prof. Carlos",7.0,8.5,8.0,8.3])
    for i in range(1, 11):
        ws.column_dimensions[chr(64+i)].width = 20

    from io import BytesIO
    bio = BytesIO()
    wb.save(bio); bio.seek(0)
    filename = f"tgi_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    resp = make_response(bio.read())
    resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
    resp.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return resp
