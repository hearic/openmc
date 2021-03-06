import re
import sys

import openmc
from openmc.checkvalue import check_type, check_length
from openmc.data import NATURAL_ABUNDANCE

if sys.version_info[0] >= 3:
    basestring = str



class Element(object):
    """A natural element used in a material via <element>. Internally, OpenMC will
    expand the natural element into isotopes based on the known natural
    abundances.

    Parameters
    ----------
    name : str
        Chemical symbol of the element, e.g. Pu
    xs : str
        Cross section identifier, e.g. 71c

    Attributes
    ----------
    name : str
        Chemical symbol of the element, e.g. Pu
    xs : str
        Cross section identifier, e.g. 71c
    scattering : {'data', 'iso-in-lab', None}
        The type of angular scattering distribution to use

    """

    def __init__(self, name='', xs=None):
        # Initialize class attributes
        self._name = ''
        self._xs = None
        self._scattering = None

        # Set class attributes
        self.name = name

        if xs is not None:
            self.xs = xs

    def __eq__(self, other):
        if isinstance(other, Element):
            if self.name != other.name:
                return False
            elif self.xs != other.xs:
                return False
            else:
                return True
        elif isinstance(other, basestring) and other == self.name:
            return True
        else:
            return False

    def __ne__(self, other):
        return not self == other

    def __gt__(self, other):
        return repr(self) > repr(other)

    def __lt__(self, other):
        return not self > other

    def __hash__(self):
        return hash(repr(self))

    def __repr__(self):
        string = 'Element    -    {0}\n'.format(self._name)
        string += '{0: <16}{1}{2}\n'.format('\tXS', '=\t', self._xs)
        if self.scattering is not None:
            string += '{0: <16}{1}{2}\n'.format('\tscattering', '=\t',
                                                self.scattering)

        return string

    @property
    def xs(self):
        return self._xs

    @property
    def name(self):
        return self._name

    @property
    def scattering(self):
        return self._scattering

    @xs.setter
    def xs(self, xs):
        check_type('cross section identifier', xs, basestring)
        self._xs = xs

    @name.setter
    def name(self, name):
        check_type('element name', name, basestring)
        check_length('element name', name, 1, 2)
        self._name = name

    @scattering.setter
    def scattering(self, scattering):

        if not scattering in ['data', 'iso-in-lab']:
            msg = 'Unable to set scattering for Element to {0} ' \
                  'which is not "data" or "iso-in-lab"'.format(scattering)
            raise ValueError(msg)

        self._scattering = scattering

    def expand(self):
        """Expand natural element into its naturally-occurring isotopes.

        Returns
        -------
        isotopes : list
            Naturally-occurring isotopes of the element. Each item of the list
            is a tuple consisting of an openmc.Nuclide instance and the natural
            abundance of the isotope.

        """

        isotopes = []
        for isotope, abundance in sorted(NATURAL_ABUNDANCE.items()):
            if re.match(r'{}\d+'.format(self.name), isotope):
                nuc = openmc.Nuclide(isotope, self.xs)
                isotopes.append((nuc, abundance))
        return isotopes
