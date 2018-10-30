"""
The latest version of this package is available at:
<http://github.com/jantman/wifi-survey-heatmap>

##################################################################################
Copyright 2017 Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>

    This file is part of wifi-survey-heatmap, also known as wifi-survey-heatmap.

    wifi-survey-heatmap is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    wifi-survey-heatmap is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with wifi-survey-heatmap.  If not, see <http://www.gnu.org/licenses/>.

The Copyright and Authors attributions contained herein may not be removed or
otherwise altered, except to add the Author attribution of a contributor to
this work. (Additional Terms pursuant to Section 7b of the AGPL v3)
##################################################################################
While not legally required, I sincerely request that anyone who finds
bugs please submit them at <https://github.com/jantman/wifi-survey-heatmap> or
to me via email, and that you send any contributions or improvements
either as a pull request on GitHub, or to me via email.
##################################################################################

AUTHORS:
Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>
##################################################################################
"""

import sys
import argparse
import logging
import json

from collections import defaultdict
import numpy as np
import matplotlib.cm as cm
import matplotlib.pyplot as pp
from scipy.interpolate import Rbf
from pylab import imread, imshow
from matplotlib.offsetbox import AnchoredText
from matplotlib.patheffects import withStroke
import matplotlib


FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


WIFI_CHANNELS = {
    # center frequency to (channel, bandwidth MHz)
    2412: (1, 20),
    2417: (2, 20),
    2422: (3, 20),
    2427: (4, 20),
    2432: (5, 20),
    2437: (6, 20),
    2442: (7, 20),
    2447: (8, 20),
    2452: (9, 20),
    2457: (10, 20),
    2462: (11, 20),
    2467: (12, 20),
    2472: (13, 20),
    2484: (14, 20),
    5160: (32, 20),
    5170: (34, 40),
    5180: (36, 20),
    5190: (38, 40),
    5200: (40, 20),
    5210: (42, 80),
    5220: (44, 20),
    5230: (46, 40),
    5240: (48, 20),
    5250: (50, 160),
    5260: (52, 20),
    5270: (54, 40),
    5280: (56, 20),
    5290: (58, 80),
    5300: (60, 20),
    5310: (62, 40),
    5320: (64, 20),
    5340: (68, 20),
    5480: (96, 20),
    5500: (100, 20),
    5510: (102, 40),
    5520: (104, 20),
    5530: (106, 80),
    5540: (108, 20),
    5550: (110, 40),
    5560: (112, 20),
    5570: (114, 160),
    5580: (116, 20),
    5590: (118, 40),
    5600: (120, 20),
    5610: (122, 80),
    5620: (124, 20),
    5630: (126, 40),
    5640: (128, 20),
    5660: (132, 20),
    5670: (134, 40),
    5680: (136, 20),
    5690: (138, 80),
    5700: (140, 20),
    5710: (142, 40),
    5720: (144, 20),
    5745: (149, 20),
    5755: (151, 40),
    5765: (153, 20),
    5775: (155, 80),
    5785: (157, 20),
    5795: (159, 40),
    5805: (161, 20),
    5825: (165, 20)
}


class HeatMapGenerator(object):

    def __init__(self, image_path, title, ignore_ssids=[]):
        self._image_path = image_path
        self._title = title
        self._ignore_ssids = ignore_ssids
        logger.debug(
            'Initialized HeatMapGenerator; image_path=%s title=%s',
            self._image_path, self._title
        )
        self._layout = imread(self._image_path)
        self._image_width = len(self._layout[0])
        self._image_height = len(self._layout) - 1
        logger.debug(
            'Loaded image with width=%d height=%d',
            self._image_width, self._image_height
        )
        with open('%s.json' % self._title, 'r') as fh:
            self._data = json.loads(fh.read())
        logger.info('Loaded %d measurement points', len(self._data))

    def generate(self):
        a = defaultdict(list)
        for row in self._data:
            a['x'].append(row['x'])
            a['y'].append(row['y'])
            a['rssi'].append(row['result']['iwconfig']['stats']['level'])
            a['quality'].append(row['result']['iwconfig']['stats']['quality'])
            a['tcp_upload_Mbps'].append(row['result']['tcp']['sent_Mbps'])
            a['tcp_download_Mbps'].append(
                row['result']['tcp-reverse']['received_Mbps']
            )
            a['udp_Mbps'].append(row['result']['udp']['Mbps'])
            a['jitter'].append(row['result']['udp']['jitter_ms'])
        for x, y in [
            (0, 0), (0, self._image_height),
            (self._image_width, 0), (self._image_width, self._image_height)
        ]:
            a['x'].append(x)
            a['y'].append(y)
            for k in a.keys():
                if k in ['x', 'y']:
                    continue
                a[k].append(min(a[k]))
        self._plot_channels()
        num_x = int(self._image_width / 4)
        num_y = int(num_x / (self._image_width / self._image_height))
        x = np.linspace(0, self._image_width, num_x)
        y = np.linspace(0, self._image_height, num_y)
        gx, gy = np.meshgrid(x, y)
        gx, gy = gx.flatten(), gy.flatten()
        for k, ptitle in {
            'rssi': 'RSSI (level)',
            'quality': 'iwstats Quality',
            'tcp_upload_Mbps': 'TCP Upload Mbps',
            'tcp_download_Mbps': 'TCP Download Mbps',
            'udp_Mbps': 'UDP Upload Mbps',
            'jitter': 'UDP Jitter (ms)'
        }.items():
            self._plot(
                a, k, '%s - %s' % (self._title, ptitle), gx, gy, num_x, num_y
            )

    def _plot_channels(self):
        channels = defaultdict(list)
        for row in self._data:
            for scan in row['result']['iwscan']:
                if scan['ESSID'] in self._ignore_ssids:
                    continue
                channels[scan['Frequency'] / 1000000].append(
                    scan['stats']['quality']
                )
        for freq in channels.keys():
            channels[freq] = sum(channels[freq]) / len(channels[freq])
        print(channels)
        raise NotImplementedError()
        pp.close('all')

    def _add_inner_title(self, ax, title, loc, size=None, **kwargs):
        if size is None:
            size = dict(size=pp.rcParams['legend.fontsize'])
        at = AnchoredText(
            title, loc=loc, prop=size, pad=0., borderpad=0.5, frameon=False,
            **kwargs
        )
        at.set_zorder(200)
        ax.add_artist(at)
        at.txt._text.set_path_effects(
            [withStroke(foreground="w", linewidth=3)]
        )
        return at

    def _plot(self, a, key, title, gx, gy, num_x, num_y):
        pp.rcParams['figure.figsize'] = (
            self._image_width / 300, self._image_height / 300
        )
        pp.title(title)
        # Interpolate the data
        rbf = Rbf(
            a['x'], a['y'], a[key], function='linear'
        )
        z = rbf(gx, gy)
        z = z.reshape((num_y, num_x))
        # Render the interpolated data to the plot
        pp.axis('off')
        # begin color mapping
        norm = matplotlib.colors.Normalize(
            vmin=min(a[key]), vmax=max(a[key]), clip=True
        )
        mapper = cm.ScalarMappable(norm=norm, cmap='RdYlBu_r')
        # end color mapping
        image = pp.imshow(
            z,
            extent=(0, self._image_width, self._image_height, 0),
            cmap='RdYlBu_r', alpha=0.5, zorder=100
        )
        pp.colorbar(image)
        pp.imshow(self._layout, interpolation='bicubic', zorder=1, alpha=1)
        # begin plotting points
        for idx in range(0, len(a['x'])):
            pp.plot(
                a['x'][idx], a['y'][idx],
                marker='o', markeredgecolor='black', markeredgewidth=1,
                markerfacecolor=mapper.to_rgba(a[key][idx]), markersize=6
            )
        # end plotting points
        fname = '%s_%s.png' % (key, self._title)
        logger.info('Writing plot to: %s', fname)
        pp.savefig(fname, dpi=300)
        pp.close('all')


def parse_args(argv):
    """
    parse arguments/options

    this uses the new argparse module instead of optparse
    see: <https://docs.python.org/2/library/argparse.html>
    """
    p = argparse.ArgumentParser(description='wifi survey heatmap generator')
    p.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                   help='verbose output. specify twice for debug-level output.')
    p.add_argument('-i', '--ignore', dest='ignore', action='append',
                   default=[], help='SSIDs to ignore from channel graph')
    p.add_argument('IMAGE', type=str, help='Path to background image')
    p.add_argument(
        'TITLE', type=str, help='Title for survey (and data filename)'
    )
    args = p.parse_args(argv)
    return args


def set_log_info():
    """set logger level to INFO"""
    set_log_level_format(logging.INFO,
                         '%(asctime)s %(levelname)s:%(name)s:%(message)s')


def set_log_debug():
    """set logger level to DEBUG, and debug-level output format"""
    set_log_level_format(
        logging.DEBUG,
        "%(asctime)s [%(levelname)s %(filename)s:%(lineno)s - "
        "%(name)s.%(funcName)s() ] %(message)s"
    )


def set_log_level_format(level, format):
    """
    Set logger level and format.

    :param level: logging level; see the :py:mod:`logging` constants.
    :type level: int
    :param format: logging formatter format string
    :type format: str
    """
    formatter = logging.Formatter(fmt=format)
    logger.handlers[0].setFormatter(formatter)
    logger.setLevel(level)


def main():
    args = parse_args(sys.argv[1:])

    # set logging level
    if args.verbose > 1:
        set_log_debug()
    elif args.verbose == 1:
        set_log_info()

    HeatMapGenerator(
        args.IMAGE, args.TITLE, ignore_ssids=args.ignore
    ).generate()


if __name__ == '__main__':
    main()
