

def iframe_url(target, width=500, height=400, scrolling=True, border=0, frameborder=0):
    """Produce an iframe for displaying an item in HTML window.
    :param target: the target url.
    :type target: string
    :param width: the width of the iframe (default 500).
    :type width: int
    :param height: the height of the iframe (default 400).
    :type height: int
    :param scrolling: whether or not to allow scrolling (default True).
    :type scrolling: bool
    :param border: width of the border.
    :type border: int
    :param frameborder: width of the frameborder.
    :type frameborder: int"""

    prefix = u"http://" if not target.startswith("http") else u""
    target = prefix + target
    if scrolling:
        scroll_val = "yes"
    else:
        scroll_val = "no"
    return u'<iframe frameborder="{frameborder}" scrolling="{scrolling}" style="border:{border}px" src="{url}", width={width} height={height}></iframe>'.format(
        frameborder=frameborder,
        scrolling=scroll_val,
        border=border,
        url=target,
        width=width,
        height=height,
    )
