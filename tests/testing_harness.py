from __future__ import print_function

import filecmp
import glob
import hashlib
from optparse import OptionParser
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.pardir, os.pardir))
from input_set import InputSet, MGInputSet
import openmc


class TestHarness(object):
    """General class for running OpenMC regression tests."""

    def __init__(self, statepoint_name, tallies_present=False):
        self._sp_name = statepoint_name
        self._tallies = tallies_present
        self.parser = OptionParser()
        self.parser.add_option('--exe', dest='exe', default='openmc')
        self.parser.add_option('--mpi_exec', dest='mpi_exec', default=None)
        self.parser.add_option('--mpi_np', dest='mpi_np', type=int, default=3)
        self.parser.add_option('--update', dest='update', action='store_true',
                               default=False)
        self._opts = None
        self._args = None

    def main(self):
        """Accept commandline arguments and either run or update tests."""
        (self._opts, self._args) = self.parser.parse_args()
        if self._opts.update:
            self.update_results()
        else:
            self.execute_test()

    def execute_test(self):
        """Run OpenMC with the appropriate arguments and check the outputs."""
        try:
            self._run_openmc()
            self._test_output_created()
            results = self._get_results()
            self._write_results(results)
            self._compare_results()
        finally:
            self._cleanup()

    def update_results(self):
        """Update the results_true using the current version of OpenMC."""
        try:
            self._run_openmc()
            self._test_output_created()
            results = self._get_results()
            self._write_results(results)
            self._overwrite_results()
        finally:
            self._cleanup()

    def _run_openmc(self):
        if self._opts.mpi_exec is not None:
            returncode = openmc.run(mpi_procs=self._opts.mpi_np,
                                    openmc_exec=self._opts.exe,
                                    mpi_exec=self._opts.mpi_exec)

        else:
            returncode = openmc.run(openmc_exec=self._opts.exe)

        assert returncode == 0, 'OpenMC did not exit successfully.'

    def _test_output_created(self):
        """Make sure statepoint.* and tallies.out have been created."""
        statepoint = glob.glob(os.path.join(os.getcwd(), self._sp_name))
        assert len(statepoint) == 1, 'Either multiple or no statepoint files' \
            ' exist.'
        assert statepoint[0].endswith('h5'), \
            'Statepoint file is not a HDF5 file.'
        if self._tallies:
            assert os.path.exists(os.path.join(os.getcwd(), 'tallies.out')), \
                'Tally output file does not exist.'

    def _get_results(self, hash_output=False):
        """Digest info in the statepoint and return as a string."""
        # Read the statepoint file.
        statepoint = glob.glob(os.path.join(os.getcwd(), self._sp_name))[0]
        sp = openmc.StatePoint(statepoint)

        # Write out k-combined.
        outstr = 'k-combined:\n'
        form = '{0:12.6E} {1:12.6E}\n'
        outstr += form.format(sp.k_combined[0], sp.k_combined[1])

        # Write out tally data.
        if self._tallies:
            tally_num = 1
            for tally_ind in sp.tallies:
                tally = sp.tallies[tally_ind]
                results = np.zeros((tally.sum.size * 2, ))
                results[0::2] = tally.sum.ravel()
                results[1::2] = tally.sum_sq.ravel()
                results = ['{0:12.6E}'.format(x) for x in results]

                outstr += 'tally ' + str(tally_num) + ':\n'
                outstr += '\n'.join(results) + '\n'
                tally_num += 1

        # Hash the results if necessary.
        if hash_output:
            sha512 = hashlib.sha512()
            sha512.update(outstr.encode('utf-8'))
            outstr = sha512.hexdigest()

        return outstr

    def _write_results(self, results_string):
        """Write the results to an ASCII file."""
        with open('results_test.dat', 'w') as fh:
            fh.write(results_string)

    def _overwrite_results(self):
        """Overwrite the results_true with the results_test."""
        shutil.copyfile('results_test.dat', 'results_true.dat')

    def _compare_results(self):
        """Make sure the current results agree with the _true standard."""
        compare = filecmp.cmp('results_test.dat', 'results_true.dat')
        if not compare:
            os.rename('results_test.dat', 'results_error.dat')
        assert compare, 'Results do not agree.'

    def _cleanup(self):
        """Delete statepoints, tally, and test files."""
        output = glob.glob(os.path.join(os.getcwd(), 'statepoint.*.h5'))
        output.append(os.path.join(os.getcwd(), 'tallies.out'))
        output.append(os.path.join(os.getcwd(), 'results_test.dat'))
        output.append(os.path.join(os.getcwd(), 'summary.h5'))
        output += glob.glob(os.path.join(os.getcwd(), 'volume_*.h5'))
        for f in output:
            if os.path.exists(f):
                os.remove(f)


class HashedTestHarness(TestHarness):
    """Specialized TestHarness that hashes the results."""

    def _get_results(self):
        """Digest info in the statepoint and return as a string."""
        return super(HashedTestHarness, self)._get_results(True)


class CMFDTestHarness(TestHarness):
    """Specialized TestHarness for running OpenMC CMFD tests."""

    def _get_results(self):
        """Digest info in the statepoint and return as a string."""
        # Read the statepoint file.
        statepoint = glob.glob(os.path.join(os.getcwd(), self._sp_name))[0]
        sp = openmc.StatePoint(statepoint)

        # Write out the eigenvalue and tallies.
        outstr = super(CMFDTestHarness, self)._get_results()

        # Write out CMFD data.
        outstr += 'cmfd indices\n'
        outstr += '\n'.join(['{0:12.6E}'.format(x) for x in sp.cmfd_indices])
        outstr += '\nk cmfd\n'
        outstr += '\n'.join(['{0:12.6E}'.format(x) for x in sp.k_cmfd])
        outstr += '\ncmfd entropy\n'
        outstr += '\n'.join(['{0:12.6E}'.format(x) for x in sp.cmfd_entropy])
        outstr += '\ncmfd balance\n'
        outstr += '\n'.join(['{0:12.6E}'.format(x) for x in sp.cmfd_balance])
        outstr += '\ncmfd dominance ratio\n'
        outstr += '\n'.join(['{0:10.3E}'.format(x) for x in sp.cmfd_dominance])
        outstr += '\ncmfd openmc source comparison\n'
        outstr += '\n'.join(['{0:12.6E}'.format(x) for x in sp.cmfd_srccmp])
        outstr += '\ncmfd source\n'
        cmfdsrc = np.reshape(sp.cmfd_src, np.product(sp.cmfd_indices),
                             order='F')
        outstr += '\n'.join(['{0:12.6E}'.format(x) for x in cmfdsrc])
        outstr += '\n'

        return outstr


class ParticleRestartTestHarness(TestHarness):
    """Specialized TestHarness for running OpenMC particle restart tests."""

    def _run_openmc(self):
        # Set arguments
        args = {'openmc_exec': self._opts.exe}
        if self._opts.mpi_exec is not None:
            args.update({'mpi_procs': self._opts.mpi_np,
                         'mpi_exec': self._opts.mpi_exec})

        # Initial run
        returncode = openmc.run(**args)
        assert returncode == 0, 'OpenMC did not exit successfully.'

        # Run particle restart
        args.update({'restart_file': self._sp_name})
        returncode = openmc.run(**args)
        assert returncode == 0, 'OpenMC did not exit successfully.'

    def _test_output_created(self):
        """Make sure the restart file has been created."""
        particle = glob.glob(os.path.join(os.getcwd(), self._sp_name))
        assert len(particle) == 1, 'Either multiple or no particle restart ' \
            'files exist.'
        assert particle[0].endswith('h5'), \
            'Particle restart file is not a HDF5 file.'

    def _get_results(self):
        """Digest info in the statepoint and return as a string."""
        # Read the particle restart file.
        particle = glob.glob(os.path.join(os.getcwd(), self._sp_name))[0]
        p = openmc.Particle(particle)

        # Write out the properties.
        outstr = ''
        outstr += 'current batch:\n'
        outstr += "{0:12.6E}\n".format(p.current_batch)
        outstr += 'current gen:\n'
        outstr += "{0:12.6E}\n".format(p.current_gen)
        outstr += 'particle id:\n'
        outstr += "{0:12.6E}\n".format(p.id)
        outstr += 'run mode:\n'
        outstr += "{0}\n".format(p.run_mode)
        outstr += 'particle weight:\n'
        outstr += "{0:12.6E}\n".format(p.weight)
        outstr += 'particle energy:\n'
        outstr += "{0:12.6E}\n".format(p.energy)
        outstr += 'particle xyz:\n'
        outstr += "{0:12.6E} {1:12.6E} {2:12.6E}\n".format(p.xyz[0], p.xyz[1],
                                                           p.xyz[2])
        outstr += 'particle uvw:\n'
        outstr += "{0:12.6E} {1:12.6E} {2:12.6E}\n".format(p.uvw[0], p.uvw[1],
                                                           p.uvw[2])

        return outstr


class PyAPITestHarness(TestHarness):
    def __init__(self, statepoint_name, tallies_present=False, mg=False):
        super(PyAPITestHarness, self).__init__(statepoint_name,
                                               tallies_present)
        self.parser.add_option('--build-inputs', dest='build_only',
                               action='store_true', default=False)
        if mg:
            self._input_set = MGInputSet()
        else:
            self._input_set = InputSet()

    def main(self):
        """Accept commandline arguments and either run or update tests."""
        (self._opts, self._args) = self.parser.parse_args()
        if self._opts.build_only:
            self._build_inputs()
        elif self._opts.update:
            self.update_results()
        else:
            self.execute_test()

    def execute_test(self):
        """Build input XMLs, run OpenMC, and verify correct results."""
        try:
            self._build_inputs()
            inputs = self._get_inputs()
            self._write_inputs(inputs)
            self._compare_inputs()
            self._run_openmc()
            self._test_output_created()
            results = self._get_results()
            self._write_results(results)
            self._compare_results()
        finally:
            self._cleanup()

    def update_results(self):
        """Update results_true.dat and inputs_true.dat"""
        try:
            self._build_inputs()
            inputs = self._get_inputs()
            self._write_inputs(inputs)
            self._overwrite_inputs()
            self._run_openmc()
            self._test_output_created()
            results = self._get_results()
            self._write_results(results)
            self._overwrite_results()
        finally:
            self._cleanup()

    def _build_inputs(self):
        """Write input XML files."""
        self._input_set.build_default_materials_and_geometry()
        self._input_set.build_default_settings()
        self._input_set.export()

    def _get_inputs(self):
        """Return a hash digest of the input XML files."""
        xmls = ('geometry.xml', 'tallies.xml', 'materials.xml', 'settings.xml',
                'plots.xml')
        xmls = [os.path.join(os.getcwd(), fname) for fname in xmls]
        outstr = '\n'.join([open(fname).read() for fname in xmls
                            if os.path.exists(fname)])

        sha512 = hashlib.sha512()
        sha512.update(outstr.encode('utf-8'))
        outstr = sha512.hexdigest()

        return outstr

    def _write_inputs(self, input_digest):
        """Write the digest of the input XMLs to an ASCII file."""
        with open('inputs_test.dat', 'w') as fh:
            fh.write(input_digest)

    def _overwrite_inputs(self):
        """Overwrite inputs_true.dat with inputs_test.dat"""
        shutil.copyfile('inputs_test.dat', 'inputs_true.dat')

    def _compare_inputs(self):
        """Make sure the current inputs agree with the _true standard."""
        compare = filecmp.cmp('inputs_test.dat', 'inputs_true.dat')
        if not compare:
            f = open('inputs_test.dat')
            for line in f.readlines():
                print(line)
            f.close()
            os.rename('inputs_test.dat', 'inputs_error.dat')
        assert compare, 'Input files are broken.'

    def _cleanup(self):
        """Delete XMLs, statepoints, tally, and test files."""
        super(PyAPITestHarness, self)._cleanup()
        output = [os.path.join(os.getcwd(), 'materials.xml')]
        output.append(os.path.join(os.getcwd(), 'geometry.xml'))
        output.append(os.path.join(os.getcwd(), 'settings.xml'))
        output.append(os.path.join(os.getcwd(), 'inputs_test.dat'))
        output.append(os.path.join(os.getcwd(), 'summary.h5'))
        for f in output:
            if os.path.exists(f):
                os.remove(f)
