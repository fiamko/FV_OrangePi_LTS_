from flask import Blueprint, render_template

from services.statistics_service import get_hourly_details, get_statistics_overview


statistics_bp = Blueprint("statistics", __name__)


@statistics_bp.route("/statistiky")
def statistics():
    """Jednoduchy prehled statistik z ulozene historie."""
    return render_template("statistics.html", stats=get_statistics_overview())


@statistics_bp.route("/statistiky/detail")
def statistics_detail():
    """Detailni hodinovy pohled za poslednich 24 hodin."""
    return render_template("statistics_detail.html", rows=get_hourly_details())
