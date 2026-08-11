from flask import Blueprint, jsonify, render_template, request, Response

from services.statistics_service import (
    export_csv,
    get_graph_data,
    get_hourly_details,
    get_statistics_overview,
)


statistics_bp = Blueprint("statistics", __name__)


@statistics_bp.route("/statistiky")
def statistics():
    """Jednoduchy prehled statistik z ulozene historie."""
    return render_template("statistics.html", stats=get_statistics_overview())


@statistics_bp.route("/statistiky/detail")
def statistics_detail():
    """Detailni hodinovy pohled za poslednich 24 hodin."""
    return render_template("statistics_detail.html", rows=get_hourly_details())


@statistics_bp.route("/statistiky/grafy")
def statistics_graphs():
    """Interaktivni grafy."""
    return render_template("statistics_graphs.html")


@statistics_bp.route("/statistiky/data")
def statistics_data():
    """API: vrati data pro grafy jako JSON."""
    period = request.args.get("period", "24h")
    return jsonify(get_graph_data(period))


@statistics_bp.route("/statistiky/export")
def statistics_export():
    """Export dat jako CSV."""
    period = request.args.get("period", "30d")
    csv_data = export_csv(period)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=fve_{period}.csv"},
    )
