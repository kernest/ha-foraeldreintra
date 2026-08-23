import html as html_module
import json
from datetime import date

import pytest

from custom_components.foraeldreintra.api_parser import (
    _clean_child_name,
    _dk_date_to_iso,
    _extract_all_weekplans_from_list,
    _extract_diary_id,
    _extract_latest_weekplan_from_list,
    _html_to_text,
    _parse_homework_notes,
    _parse_weekplan_page,
    _select_best_weekplan,
    _select_weekplans_by_offset,
)


class TestDkDateToIso:
    def test_full_danish_date(self):
        assert _dk_date_to_iso("15. januar 2024") == "2024-01-15"

    def test_date_with_day_name_prefix(self):
        assert _dk_date_to_iso("mandag, 15. januar 2024") == "2024-01-15"

    def test_abbreviated_month(self):
        assert _dk_date_to_iso("3. feb 2024") == "2024-02-03"

    def test_single_digit_day_is_zero_padded(self):
        assert _dk_date_to_iso("5. maj 2024") == "2024-05-05"

    def test_none_returns_none(self):
        assert _dk_date_to_iso(None) is None

    def test_empty_string_returns_none(self):
        assert _dk_date_to_iso("") is None

    def test_unrecognised_format_returns_original(self):
        assert _dk_date_to_iso("invalid date") == "invalid date"

    @pytest.mark.parametrize("month_name,expected_num", [
        ("januar", 1), ("februar", 2), ("marts", 3), ("april", 4),
        ("maj", 5), ("juni", 6), ("juli", 7), ("august", 8),
        ("september", 9), ("oktober", 10), ("november", 11), ("december", 12),
    ])
    def test_all_danish_month_names(self, month_name, expected_num):
        result = _dk_date_to_iso(f"1. {month_name} 2024")
        assert result == f"2024-{expected_num:02d}-01"

    @pytest.mark.parametrize("abbrev,expected_num", [
        ("jan", 1), ("feb", 2), ("mar", 3), ("apr", 4),
        ("jun", 6), ("jul", 7), ("aug", 8), ("sep", 9),
        ("okt", 10), ("nov", 11), ("dec", 12),
    ])
    def test_abbreviated_month_names(self, abbrev, expected_num):
        result = _dk_date_to_iso(f"1. {abbrev} 2024")
        assert result == f"2024-{expected_num:02d}-01"


class TestCleanChildName:
    def test_removes_item_suffix_lowercase(self):
        assert _clean_child_name("AnnaItem") == "Anna"

    def test_removes_item_suffix_uppercase(self):
        assert _clean_child_name("AnnaITEM") == "Anna"

    def test_name_without_item_suffix_unchanged(self):
        assert _clean_child_name("Anna") == "Anna"

    def test_strips_surrounding_whitespace(self):
        assert _clean_child_name("  Anna  ") == "Anna"

    def test_empty_string_stays_empty(self):
        assert _clean_child_name("") == ""


class TestExtractDiaryId:
    def test_extracts_id_from_weeklyplans_url(self):
        html = '<a href="/parent/123/anna/item/weeklyplansandhomework/diary/456">link</a>'
        assert _extract_diary_id(html) == "456"

    def test_extracts_id_from_diary_slash_pattern(self):
        assert _extract_diary_id('href="/diary/789/"') == "789"

    def test_extracts_id_from_diary_quote_pattern(self):
        assert _extract_diary_id('diary/321"') == "321"

    def test_returns_none_when_no_diary_id(self):
        assert _extract_diary_id("<html>ingen dagbog her</html>") is None

    def test_returns_none_for_empty_string(self):
        assert _extract_diary_id("") is None


class TestHtmlToText:
    def test_plain_paragraph(self):
        assert _html_to_text("<p>Hej verden</p>") == "Hej verden"

    def test_br_tag_becomes_newline(self):
        result = _html_to_text("<p>Linje1<br>Linje2</p>")
        assert "Linje1" in result
        assert "Linje2" in result

    def test_empty_input_returns_empty_string(self):
        assert _html_to_text("") == ""

    def test_strips_html_tags(self):
        assert _html_to_text("<p>Fed og kursiv</p>") == "Fed og kursiv"

    def test_non_breaking_space_replaced(self):
        result = _html_to_text("<p>Hej\xa0verden</p>")
        assert "\xa0" not in result

    def test_empty_lines_removed(self):
        result = _html_to_text("<p>A</p><p></p><p>B</p>")
        assert result == "A\nB"

    def test_red_text_becomes_bold(self):
        result = _html_to_text('<span style="color: red">HUSK dette</span>')
        assert "**HUSK dette**" in result

    def test_colored_span_becomes_bold(self):
        result = _html_to_text('<span style="color: #c0392b">Vigtigt!</span>')
        assert "**Vigtigt!**" in result

    def test_rgb_color_becomes_bold(self):
        result = _html_to_text('<span style="color: rgb(255, 0, 0)">OBS</span>')
        assert "**OBS**" in result

    def test_black_text_stays_plain(self):
        result = _html_to_text('<span style="color: black">Normal tekst</span>')
        assert "**" not in result
        assert "Normal tekst" in result

    def test_black_hex_stays_plain(self):
        result = _html_to_text('<span style="color: #000000">Normal</span>')
        assert "**" not in result

    def test_strong_tag_becomes_bold(self):
        result = _html_to_text("<p>Hej <strong>verden</strong></p>")
        assert "**verden**" in result

    def test_em_tag_becomes_italic(self):
        result = _html_to_text("<p>Hej <em>verden</em></p>")
        assert "_verden_" in result

    def test_mixed_color_and_plain(self):
        result = _html_to_text(
            '<p>Normal tekst <span style="color:red">VIGTIGT</span> mere tekst</p>'
        )
        assert "**VIGTIGT**" in result
        assert "Normal tekst" in result
        assert "mere tekst" in result


class TestParseHomeworkNotes:
    def test_empty_html_returns_empty_list(self):
        assert _parse_homework_notes("") == []

    def test_parses_single_homework_item(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"><b>Mandag, 15. januar 2024:</b></div>
            <div class="sk-user-input">
              <p><strong>Dansk:</strong></p>
              <p>Læs side 42</p>
            </div>
          </li>
        </ul>
        """
        result = _parse_homework_notes(html)
        assert len(result) == 1
        assert result[0]["dato"] == "Mandag, 15. januar 2024"
        assert result[0]["fag"] == "Dansk"
        assert "Læs side 42" in result[0]["tekst"]
        assert result[0]["links"] == []

    def test_item_without_date_tag_is_skipped(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"></div>
            <div class="sk-user-input"><p>Noget tekst</p></div>
          </li>
        </ul>
        """
        assert _parse_homework_notes(html) == []

    def test_item_without_content_div_is_skipped(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"><b>Dato:</b></div>
          </li>
        </ul>
        """
        assert _parse_homework_notes(html) == []

    def test_links_are_extracted(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"><b>15. januar 2024:</b></div>
            <div class="sk-user-input">
              <p><a href="https://example.com">Klik her</a></p>
            </div>
          </li>
        </ul>
        """
        result = _parse_homework_notes(html)
        assert len(result) == 1
        assert len(result[0]["links"]) == 1
        assert result[0]["links"][0]["url"] == "https://example.com"
        assert result[0]["links"][0]["tekst"] == "Klik her"


class TestParseHomeworkNotesLektiebogTable:
    def test_table_rows_split_into_separate_subjects(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"><b>Onsdag, 15. apr. 2026:</b></div>
            <div class="sk-user-input">
              <table>
                <tr><th>FAG</th><th>LEKTIER</th></tr>
                <tr><td>DANSK</td><td>Læs side 100-103 i Kom og Læs</td></tr>
                <tr><td>MATEMATIK</td><td>Lav side 38 færdig</td></tr>
                <tr><td>ENGELSK</td><td></td></tr>
                <tr><td>IDRÆT</td><td></td></tr>
              </table>
            </div>
          </li>
        </ul>
        """
        result = _parse_homework_notes(html)

        assert len(result) == 2
        assert result[0]["dato"] == "Onsdag, 15. apr. 2026"
        assert result[0]["fag"] == "Dansk"
        assert "Læs side 100-103" in result[0]["tekst"]
        assert result[1]["fag"] == "Matematik"
        assert "Lav side 38 færdig" in result[1]["tekst"]

    def test_empty_subject_rows_are_skipped(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"><b>15. apr. 2026:</b></div>
            <div class="sk-user-input">
              <table>
                <tr><th>FAG</th><th>LEKTIER</th></tr>
                <tr><td>ENGELSK</td><td></td></tr>
                <tr><td>MUSIK</td><td>   </td></tr>
              </table>
            </div>
          </li>
        </ul>
        """
        assert _parse_homework_notes(html) == []

    def test_table_links_are_extracted(self):
        html = """
        <ul class="sk-list">
          <li>
            <div class="sk-white-box"><b>15. apr. 2026:</b></div>
            <div class="sk-user-input">
              <table>
                <tr><th>FAG</th><th>LEKTIER</th></tr>
                <tr><td>DANSK</td><td><a href="https://example.com">Se opgave</a></td></tr>
              </table>
            </div>
          </li>
        </ul>
        """
        result = _parse_homework_notes(html)
        assert len(result) == 1
        assert result[0]["fag"] == "Dansk"
        assert result[0]["links"][0]["url"] == "https://example.com"
        assert result[0]["links"][0]["tekst"] == "Se opgave"


class TestExtractLatestWeekplanFromList:
    def test_returns_none_for_html_without_container(self):
        assert _extract_latest_weekplan_from_list("<html></html>") is None

    def test_extracts_first_weekplan_link(self):
        html = """
        <ul class="sk-weekly-plans-list-container">
          <li>
            <a href="/parent/123/anna/item/weeklyplansandhomework/item/class/23-2024">
              Uge 23
            </a>
          </li>
        </ul>
        """
        result = _extract_latest_weekplan_from_list(html)
        assert result is not None
        assert result["weekplan_id"] == "23-2024"
        assert "Uge 23" in result["title"]
        assert "class/23-2024" in result["href"]

    def test_returns_none_when_no_matching_link(self):
        html = """
        <ul class="sk-weekly-plans-list-container">
          <li><a href="/other/path">Noget andet</a></li>
        </ul>
        """
        assert _extract_latest_weekplan_from_list(html) is None

    def test_returns_none_for_empty_string(self):
        assert _extract_latest_weekplan_from_list("") is None

    def test_selects_current_week_over_future(self):
        html = """
        <ul class="sk-weekly-plans-list-container">
          <li>
            <a href="/item/weeklyplansandhomework/item/class/36-2026">Uge 36</a>
          </li>
          <li>
            <a href="/item/weeklyplansandhomework/item/class/35-2026">Uge 35</a>
          </li>
          <li>
            <a href="/item/weeklyplansandhomework/item/class/34-2026">Uge 34</a>
          </li>
        </ul>
        """
        # 2026-08-25 is a Monday in ISO week 35
        result = _extract_latest_weekplan_from_list(html, today=date(2026, 8, 25))
        assert result is not None
        assert result["weekplan_id"] == "35-2026"


class TestSelectBestWeekplan:
    def _make_plan(self, week_id: str) -> dict[str, str]:
        return {
            "weekplan_id": week_id,
            "href": f"/item/class/{week_id}",
            "title": f"Uge {week_id}",
        }

    def test_returns_none_for_empty_list(self):
        assert _select_best_weekplan([], today=date(2026, 8, 24)) is None

    def test_returns_single_plan(self):
        plans = [self._make_plan("35-2026")]
        result = _select_best_weekplan(plans, today=date(2026, 8, 24))
        assert result["weekplan_id"] == "35-2026"

    def test_picks_current_week(self):
        plans = [
            self._make_plan("36-2026"),
            self._make_plan("35-2026"),
            self._make_plan("34-2026"),
        ]
        # 2026-08-24 is ISO week 35
        result = _select_best_weekplan(plans, today=date(2026, 8, 24))
        assert result["weekplan_id"] == "35-2026"

    def test_prefers_past_over_future_when_equidistant(self):
        plans = [
            self._make_plan("36-2026"),
            self._make_plan("34-2026"),
        ]
        # week 35 — both are 1 week away; past (34) has negative diff, sorted first
        result = _select_best_weekplan(plans, today=date(2026, 8, 24))
        assert result["weekplan_id"] == "34-2026"

    def test_picks_nearest_when_no_exact_match(self):
        plans = [
            self._make_plan("37-2026"),
            self._make_plan("33-2026"),
        ]
        # week 35 — 33 is 2 away, 37 is 2 away; past preferred
        result = _select_best_weekplan(plans, today=date(2026, 8, 24))
        assert result["weekplan_id"] == "33-2026"

    def test_cross_year_boundary(self):
        plans = [
            self._make_plan("02-2027"),
            self._make_plan("52-2026"),
        ]
        # 2026-12-28 is ISO week 53 of 2026
        result = _select_best_weekplan(plans, today=date(2026, 12, 28))
        assert result["weekplan_id"] == "52-2026"

    def test_extracts_all_plans_from_list(self):
        html = """
        <ul class="sk-weekly-plans-list-container">
          <li>
            <a href="/item/weeklyplansandhomework/item/class/36-2026">Uge 36</a>
          </li>
          <li>
            <a href="/item/weeklyplansandhomework/item/class/35-2026">Uge 35</a>
          </li>
        </ul>
        """
        plans = _extract_all_weekplans_from_list(html)
        assert len(plans) == 2
        assert plans[0]["weekplan_id"] == "36-2026"
        assert plans[1]["weekplan_id"] == "35-2026"


class TestSelectWeekplansByOffset:
    def _make_plan(self, week_id: str) -> dict[str, str]:
        return {
            "weekplan_id": week_id,
            "href": f"/item/class/{week_id}",
            "title": f"Uge {week_id}",
        }

    def test_empty_list_returns_all_none(self):
        result = _select_weekplans_by_offset([], today=date(2026, 8, 24))
        assert result == {"previous": None, "current": None, "next": None}

    def test_assigns_current_week(self):
        plans = [self._make_plan("35-2026")]
        # 2026-08-24 is ISO week 35
        result = _select_weekplans_by_offset(plans, today=date(2026, 8, 24))
        assert result["current"]["weekplan_id"] == "35-2026"
        assert result["previous"] is None
        assert result["next"] is None

    def test_assigns_all_three_offsets(self):
        plans = [
            self._make_plan("34-2026"),
            self._make_plan("35-2026"),
            self._make_plan("36-2026"),
        ]
        result = _select_weekplans_by_offset(plans, today=date(2026, 8, 24))
        assert result["previous"]["weekplan_id"] == "34-2026"
        assert result["current"]["weekplan_id"] == "35-2026"
        assert result["next"]["weekplan_id"] == "36-2026"

    def test_ignores_distant_weeks(self):
        plans = [
            self._make_plan("33-2026"),
            self._make_plan("35-2026"),
            self._make_plan("37-2026"),
        ]
        result = _select_weekplans_by_offset(plans, today=date(2026, 8, 24))
        assert result["current"]["weekplan_id"] == "35-2026"
        assert result["previous"] is None
        assert result["next"] is None

    def test_cross_year_boundary(self):
        plans = [
            self._make_plan("52-2026"),
            self._make_plan("53-2026"),
            self._make_plan("01-2027"),
        ]
        # 2026-12-28 is Monday of ISO week 53
        result = _select_weekplans_by_offset(plans, today=date(2026, 12, 28))
        assert result["previous"]["weekplan_id"] == "52-2026"
        assert result["current"]["weekplan_id"] == "53-2026"
        assert result["next"]["weekplan_id"] == "01-2027"


class TestParseWeekplanPage:
    def test_html_without_app_data_returns_fallback(self):
        result = _parse_weekplan_page(
            html_text="<html></html>",
            weekplan_id="23-2024",
            fallback_title="Uge 23",
            url="https://example.com/weekplan",
        )
        assert result["title"] == "Uge 23"
        assert result["week"] == "23-2024"
        assert result["items"] == []
        assert result["days"] == []

    def test_parses_class_and_week_into_title(self):
        app_data = {
            "SelectedPlan": {
                "FormattedWeek": "23",
                "ClassOrGroup": "3A",
                "GeneralPlan": {"LessonPlans": []},
                "DailyPlans": [],
            }
        }
        encoded = html_module.escape(json.dumps(app_data))
        html_text = f'<div id="root" data-clientlogic-settings-weeklyplansapp="{encoded}"></div>'

        result = _parse_weekplan_page(
            html_text=html_text,
            weekplan_id="23-2024",
            fallback_title="Fallback",
            url="https://example.com/weekplan",
        )
        assert "3A" in result["title"]
        assert "23" in result["title"]
        assert result["class_or_group"] == "3A"

    def test_parses_general_lesson_plan(self):
        app_data = {
            "SelectedPlan": {
                "FormattedWeek": "23",
                "ClassOrGroup": "3A",
                "GeneralPlan": {
                    "LessonPlans": [
                        {
                            "Subject": {"FormattedTitle": "Dansk", "Title": "Dansk"},
                            "Content": "<p>Læs kapitlet</p>",
                        }
                    ]
                },
                "DailyPlans": [],
            }
        }
        encoded = html_module.escape(json.dumps(app_data))
        html_text = f'<div id="root" data-clientlogic-settings-weeklyplansapp="{encoded}"></div>'

        result = _parse_weekplan_page(
            html_text=html_text,
            weekplan_id="23-2024",
            fallback_title="Fallback",
            url="https://example.com/weekplan",
        )
        assert len(result["items"]) == 1
        assert result["items"][0]["type"] == "general"
        assert result["items"][0]["subject"] == "Dansk"
        assert "Læs kapitlet" in result["items"][0]["content_text"]

    def test_invalid_json_in_app_data_returns_fallback(self):
        html_text = '<div id="root" data-clientlogic-settings-weeklyplansapp="not-valid-json"></div>'
        result = _parse_weekplan_page(
            html_text=html_text,
            weekplan_id="23-2024",
            fallback_title="Uge 23",
            url="https://example.com/weekplan",
        )
        assert result["title"] == "Uge 23"
        assert result["items"] == []
