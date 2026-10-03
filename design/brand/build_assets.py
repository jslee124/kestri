"""Build the official Kestri vector assets from shared, editable geometry.

Run from any directory with Python 3. PNG exports are produced separately by
render_assets.cjs. No font, embedded bitmap, network, or third-party package is
needed to build the SVG files.
"""

import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
COLORS = {
    "orange": "#CA7448",
    "cream": "#F6E5CC",
    "ink": "#30343B",
    "blue": "#63758C",
    "gold": "#EAAF56",
    "white": "#FFFCF6",
}


def path(name: str, color: str, geometry: str) -> str:
    return f'<path id="{name}" fill="{COLORS[color]}" d="{geometry}"/>'


def head() -> str:
    """The same tilted kestrel head appears in both the mascot and the mark."""
    return "\n".join(
        [
            path(
                "head-crown",
                "orange",
                "M350 337 C336 278 346 226 364 190 L351 202 L377 150 L363 164 "
                "C404 111 459 82 515 87 C601 84 656 133 659 206 "
                "C662 241 650 282 638 311 L644 361 L390 385 Z",
            ),
            path(
                "face",
                "cream",
                "M381 314 C390 284 404 261 432 238 L419 243 "
                "C441 207 474 179 518 174 L493 155 "
                "C533 153 571 171 591 204 L600 192 L608 220 "
                "C621 203 639 195 648 207 C654 220 650 254 640 284 "
                "L630 345 L627 398 L441 408 Z",
            ),
            path(
                "near-cheek",
                "ink",
                "M501 222 C481 244 472 264 464 300 C488 280 503 257 515 229 Z",
            ),
            path(
                "far-cheek",
                "ink",
                "M619 258 C616 281 620 304 626 330 C637 307 642 282 638 263 Z",
            ),
            '<ellipse id="near-eye" fill="#30343B" cx="507" cy="194" '
            'rx="26" ry="28" transform="rotate(-12 507 194)"/>',
            '<ellipse id="far-eye" fill="#30343B" cx="631" cy="232" '
            'rx="17" ry="27" transform="rotate(20 631 232)"/>',
            '<circle id="near-eye-highlight" fill="#FFFCF6" cx="514" cy="184" r="6"/>',
            '<circle id="far-eye-highlight" fill="#FFFCF6" cx="636" cy="225" r="4.5"/>',
            path(
                "beak-upper",
                "gold",
                "M535 243 C546 220 566 216 584 229 C593 235 598 245 598 253 L575 267 L549 253 Z",
            ),
            path(
                "beak-hook",
                "blue",
                "M535 243 C553 248 570 256 574 275 L577 294 "
                "C595 280 608 255 589 241 C570 230 559 254 535 243 Z",
            ),
            path(
                "beak-edge",
                "ink",
                "M535 243 C553 248 568 259 574 275 C565 261 551 253 535 243 Z",
            ),
            '<ellipse id="nostril" fill="#30343B" cx="559" cy="236" rx="4" ry="5" '
            'transform="rotate(25 559 236)"/>',
        ]
    )


def mascot() -> str:
    return "\n".join(
        [
            path(
                "tail",
                "orange",
                "M349 563 C289 677 174 780 72 837 Q52 856 77 858 "
                "C180 865 294 801 376 729 L460 612 Z",
            ),
            path(
                "tail-tip",
                "ink",
                "M143 782 C113 805 90 824 72 837 Q52 856 77 858 "
                "C122 861 170 848 213 826 L234 797 Z",
            ),
            path(
                "tail-feather",
                "cream",
                "M390 622 C327 713 246 779 181 812 C238 819 299 781 353 736 L435 650 Z",
            ),
            path(
                "far-leg",
                "gold",
                "M440 724 L463 723 L475 793 Q479 808 499 817 "
                "L526 829 Q548 835 558 856 L543 858 Q534 849 518 849 "
                "L486 846 Q477 842 476 854 L472 866 L456 865 L454 841 "
                "Q446 834 441 842 L427 856 L414 852 L428 829 Q446 819 450 806 Z",
            ),
            path(
                "near-leg",
                "gold",
                "M394 733 L416 731 L423 798 Q426 817 449 825 "
                "L476 837 Q491 843 494 861 L480 865 Q474 854 463 853 "
                "L435 847 L428 868 L412 869 L414 846 "
                "L393 846 Q380 846 371 860 L356 856 Q355 835 376 828 "
                "Q393 823 402 810 Z",
            ),
            path(
                "claws",
                "ink",
                "M357 856 Q360 839 374 838 Q380 843 371 860 Z "
                "M412 854 Q421 851 428 856 L428 868 Q424 879 419 883 Z "
                "M480 850 Q493 847 494 861 L491 873 Z "
                "M543 847 Q556 845 558 856 L554 865 Z "
                "M460 854 Q469 851 475 856 L472 866 L469 876 Z",
            ),
            path(
                "body-outline",
                "orange",
                "M392 306 C350 347 329 418 318 491 "
                "C288 552 280 646 329 725 C357 768 397 789 440 764 "
                "C490 779 588 695 637 615 C681 542 680 453 642 362 "
                "L639 289 Z",
            ),
            path(
                "breast",
                "cream",
                "M424 312 C382 386 368 442 350 515 "
                "C323 581 323 661 355 721 Q379 761 401 771 "
                "Q427 774 447 740 Q456 764 474 755 "
                "C548 715 605 654 631 579 C657 504 651 442 626 381 "
                "L625 313 Z",
            ),
            head(),
            path(
                "folded-wing-tip",
                "ink",
                "M350 329 C287 341 254 433 233 487 "
                "L147 710 Q116 761 148 748 C282 709 375 630 426 526 "
                "L489 392 Z",
            ),
            path(
                "folded-wing-blue",
                "blue",
                "M489 391 C454 449 398 488 319 530 "
                "L221 584 C201 632 169 680 147 710 "
                "C263 683 352 608 404 536 C452 482 480 441 489 391 Z",
            ),
            path(
                "folded-wing-orange",
                "orange",
                "M376 306 C321 309 290 343 267 390 "
                "C246 435 226 477 211 513 Q204 533 224 522 "
                "L211 548 Q205 559 225 553 "
                "C315 533 411 477 465 424 Q500 390 485 360 "
                "C470 327 423 310 376 306 Z",
            ),
        ]
    )


def mark() -> str:
    bust = "\n".join(
        [
            path(
                "bust-outline",
                "orange",
                "M365 289 L620 275 Q652 332 646 412 L356 412 Q341 351 365 289 Z",
            ),
            path("bust-breast", "cream", "M419 289 L620 286 L629 412 L418 412 L389 345 Z"),
            head(),
            path("bust-wing", "orange", "M356 335 Q405 330 448 368 Q464 388 465 412 L356 412 Z"),
        ]
    )
    # Clip only the lower bust; the crown, eyes and cheek markings remain intact.
    return (
        '<defs><clipPath id="bust-crop"><path '
        'd="M330 70 H680 V375 Q505 449 330 375 Z"/></clipPath></defs>\n'
        '<g transform="translate(26 22) scale(1.32) translate(-330 -70)">\n'
        f'<g clip-path="url(#bust-crop)">{bust}</g></g>'
    )


def monochrome_mark(color: str) -> str:
    geometry = mark()
    for name, value in COLORS.items():
        geometry = geometry.replace(
            f'fill="{value}"', f'fill="{"#000000" if name in {"cream", "white"} else "#FFFFFF"}"'
        )
    return (
        '<defs><mask id="mark-cutout" maskUnits="userSpaceOnUse" '
        'x="0" y="0" width="512" height="512">'
        f"{geometry}</mask></defs>\n"
        f'<rect width="512" height="512" fill="{color}" mask="url(#mark-cutout)"/>'
    )


def wordmark(color: str) -> str:
    """Custom lowercase lettering made of rounded vector strokes, never live text."""
    return (
        f'<g id="wordmark" fill="none" stroke="{color}" stroke-width="25" '
        'stroke-linecap="round" stroke-linejoin="round">\n'
        '<path id="letter-k" d="M20 20 V145 M89 65 L22 108 M49 91 L96 145"/>\n'
        '<path id="letter-e" d="M142 105 H206 C206 49 133 48 133 106 '
        'C133 145 171 160 201 137"/>\n'
        '<path id="letter-s" d="M301 74 C285 55 242 58 243 84 '
        'C244 109 307 101 307 129 C307 153 264 159 242 141"/>\n'
        '<path id="letter-t" d="M350 31 V121 Q350 150 380 143 M327 70 H377"/>\n'
        '<path id="letter-r" d="M423 145 V72 M423 98 Q441 61 470 70"/>\n'
        '<path id="letter-i" d="M513 74 V145"/>\n'
        f'<circle id="letter-i-dot" cx="513" cy="28" r="14" fill="{color}" stroke="none"/>\n'
        "</g>"
    )


def svg(title: str, width: int, height: int, content: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">\n'
        f'<title id="title">{escape(title)}</title>\n{content}\n</svg>\n'
    )


def sheet_symbol(content: str, prefix: str) -> str:
    """Keep reusable geometry IDs distinct when multiple assets share a sheet."""
    identifiers = re.findall(r'id="([^"]+)"', content)
    for identifier in identifiers:
        content = content.replace(f'id="{identifier}"', f'id="{prefix}-{identifier}"')
        content = content.replace(f"url(#{identifier})", f"url(#{prefix}-{identifier})")
    return content


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    mark_color = mark()
    mark_ink = monochrome_mark(COLORS["ink"])
    mark_reverse = monochrome_mark(COLORS["white"])
    files = {
        "kestri-mascot.svg": svg(
            "Kestri kestrel mascot",
            720,
            960,
            f'<g transform="translate(0 18)">{mascot()}</g>',
        ),
        "kestri-mark.svg": svg("Kestri mark", 512, 512, mark_color),
        "kestri-mark-ink.svg": svg("Kestri ink mark", 512, 512, mark_ink),
        "kestri-mark-reverse.svg": svg("Kestri reverse mark", 512, 512, mark_reverse),
        "kestri-wordmark.svg": svg(
            "Kestri wordmark",
            560,
            200,
            f'<g transform="translate(12 12)">{wordmark(COLORS["ink"])}</g>',
        ),
        "kestri-avatar.svg": svg(
            "Kestri avatar",
            1024,
            1024,
            f'<rect width="1024" height="1024" fill="{COLORS["white"]}"/>\n'
            f'<g transform="translate(102.4 102.4) scale(1.6)">{mark_color}</g>',
        ),
    }
    for suffix, symbol, color in [
        ("", mark_color, COLORS["ink"]),
        ("-dark", mark_color, COLORS["white"]),
        ("-ink", mark_ink, COLORS["ink"]),
        ("-reverse", mark_reverse, COLORS["white"]),
    ]:
        files[f"kestri-logo{suffix}.svg"] = svg(
            "Kestri horizontal logo",
            960,
            320,
            f'<g transform="translate(12 10) scale(.58)">{symbol}</g>\n'
            f'<g transform="translate(350 68) scale(1.08)">{wordmark(color)}</g>',
        )
    files["kestri-brand-sheet.svg"] = svg(
        "Kestri official brand sheet",
        1600,
        1100,
        f'<rect width="1600" height="1100" fill="{COLORS["white"]}"/>\n'
        f'<g transform="translate(28 52) scale(.92)">{sheet_symbol(mascot(), "mascot")}</g>\n'
        f'<g transform="translate(720 90) scale(.6)">{sheet_symbol(mark_color, "color")}</g>\n'
        f'<g transform="translate(1060 160) scale(.92)">{wordmark(COLORS["ink"])}</g>\n'
        f'<g transform="translate(765 448) scale(.4)">{sheet_symbol(mark_ink, "ink")}</g>\n'
        f'<rect x="1060" y="434" width="234" height="234" rx="40" fill="{COLORS["ink"]}"/>\n'
        '<g transform="translate(1074 448) scale(.4)">'
        f"{sheet_symbol(mark_reverse, 'reverse')}</g>\n"
        '<defs><clipPath id="circle-preview">'
        '<circle cx="877" cy="814" r="112"/></clipPath></defs>\n'
        f'<circle cx="877" cy="814" r="112" fill="{COLORS["cream"]}"/>\n'
        '<g clip-path="url(#circle-preview)">'
        '<g transform="translate(785 722) scale(.36)">'
        f"{sheet_symbol(mark_color, 'avatar')}</g></g>\n"
        + "\n".join(
            f'<circle cx="{1100 + index * 88}" cy="812" r="30" fill="{COLORS[color]}"/>'
            for index, color in enumerate(["orange", "cream", "ink", "blue", "gold"])
        ),
    )
    for name, content in files.items():
        (ASSETS / name).write_text(content, encoding="utf-8")
    print(f"Built {len(files)} standalone SVG assets in {ASSETS}")


if __name__ == "__main__":
    main()
