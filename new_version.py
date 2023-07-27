#! /usr/local/bin/python3
# /usr/bin/python3

'''
Generate new build version.  Version number can be auto generated or manually set.
The version number is of the format 'MM.nn.pp' where MM is the major number, nn is the minor number, and
pp is the patch number.


Typical usage:
  > ./new_version 8.5.0
The version is set to 8.5.0. The major number is 8. The minor number is 5. The patch number is 0.
The build number is set to 7.

  > ./new_version 1245
The build number is set to 1245. The major, minor, and patch numbers are not altered.


Autogenerated version options:
  > ./new_version --major
The major number is incremented by 1.  The existing minor number and patch numbers are set to 0.
The build number is set to 7.

  > ./new_version --minor
The major number is unchanged.  The existing minor number is incremented by 1. The patch number is set to 0.
The build number is set to 7.

  > ./new_version --patch
The major number and minor number are unchanged.  The existing patch number is incremented by 1.
The build number is set to 7.


Version 1.0 01/10/2022 by J. Kahn
  Ported to ansible from vRO.
Version 1.1 07/25/23 by J. Kahn
  Added build number support. Autogenerate version.inc version file.
Version 1.2 07/26/23 by J. Kahn
  Renamed version.inc to version.sh. Rename bash_file* to build_file*.
  Spec file build version does not allow "-" in version string.  Use ".".
  Added Scripts/create_log_bundle.sh to update version collection.
  Added ansible galaxy files to update version collection.
Version 1.3 07/26/23 by J. Kahn
  Updated version.sh fields. Added full version to version.sh


'''

import os
import sys
import errno
import time
import json
import subprocess
import errno


# Program name and version
utilName = 'new_version.py'
utilVersion = '1.3'


class build_versioning():
    sh_file = 'version.sh'
    sh_header = [ '# version include file.\n',
                   '#\n',
                   '# This file is autogenerated.\n',
                   '# BUILD is a placeholder. It is updated during the build process.\n',
                   '#\n',
                 ]
    sh_version = [ 'ANSIBLE_RELEASE_MAJOR',
                   'ANSIBLE_RELEASE_MINOR',
                   'ANSIBLE_RELEASE_PATCH',
                   'ANSIBLE_RELEASE_BUILD',
                   'ANSIBLE_VERSION',
                  ]

    version_tag = 'Ansible_VER'
    version_prefix = 'HV_Storage_Ansible-'
    version_hpe_prefix = 'HPE_Storage_Ansible-'

    build_file      = 'build_Ansible.sh'
    build_hpe_file  = 'build_Ansible_HPE.sh'

    rpm_file        = 'spec/build_rpm.spec'
    rpm_hpe_file    = 'spec/build_rpm-hpe.spec'

    script_file     = 'Scripts/create_log_bundle.sh'
    script_hpe_file = 'Scripts-HPE/create_log_bundle.sh'

    galaxy_file     = 'ansible/collection_playbooks/galaxy-hitachi.yml'
    galaxy_hpe_file = 'ansible/collection_playbooks/galaxy-hpe.yml'

    class vendorType():
        Hitachi = 0
        HPE = 1


    def _parse_version(self):
        """
        Parse version.inc and collect version.
        """
        with open(self.sh_file, 'r') as istream:
            data = istream.readlines()
        istream.close()
        #print (data)

        version = [ 0, 0, 0, 0 ]
        for line in data:
            if line.startswith('#'):
                continue
            fields = line.split('=')
            if len(fields) != 2:
                continue
            if fields[0].startswith(self.sh_version[0]):
                version[0] = int(fields[1])
            elif fields[0].startswith(self.sh_version[1]):
                version[1] = int(fields[1])
            elif fields[0].startswith(self.sh_version[2]):
                version[2] = int(fields[1])
            elif fields[0].startswith(self.sh_version[3]):
                version[3] = int(fields[1])
        return version


    def current(self):
        """
        Get the current (Hitachi) version.
        """
        version = self._parse_version()
        return version


    def _generate_sh_version(self, ofile, version):
        """
        Generate bash version file.
        """
        version_str = ( '"' + str(version[0]).rjust(2,'0') + '.' + 
                        str(version[1]) + '.' + 
                        str(version[2]) + '.' + 
                        str(version[3]) + '"')

        versionLen = len(version) - 1
        with open(ofile, 'w') as ostream:
            for line in self.sh_header:
                ostream.write(line)
            for i in range(0, versionLen):
                line = self.sh_version[i] + '=' + str(version[i]) + '\n'
                ostream.write(line)

            # If build number is 7 (typical), ensure it's '007'
            if version[-1] == 7:
                buildno = '00' + str(version[-1])
            else:
                buildno = str(version[-1])
            line = self.sh_version[-2] + '=' + buildno + '\n'
            ostream.write(line)

            line = self.sh_version[-1] + '=' + version_str + '\n'
            ostream.write(line)
        ostream.close()


    def _generate_build_version(self, vendor, build_file, version):
        """
        Generate bash version file based on vendor type.
        """
        if vendor == self.vendorType.HPE:
            version_str = self.version_tag + '=' + self.version_hpe_prefix 
        else:
            version_str = self.version_tag + '=' + self.version_prefix

        version_str += ( str(version[0]).rjust(2,'0') + '.' + 
                         str(version[1]) + '.' + 
                         str(version[2]) + '.' + 
                         str(version[3]) + '\n' )

        with open(build_file, 'r') as istream:
            data = istream.readlines()
        istream.close()

        with open(build_file, 'w') as ostream:
            for line in data:
                if line.startswith(self.version_tag):
                    line = version_str
                ostream.write(line)
        ostream.close()


    def _generate_spec_version(self, vendor, spec_file, version):
        """
        Update RPM spec file with version based on vendor type.
        """
        if vendor == self.vendorType.HPE:
            version_prefix = self.version_hpe_prefix
        else:
            version_prefix = self.version_prefix

        with open(spec_file, 'r') as istream:
            data = istream.readlines()
        istream.close()
        #print (data)

        foundVersion = False
        foundSource = False
        with open(spec_file, 'w') as ostream:
            for line in data:
                # Update RPM version.
                if not foundVersion and line.startswith('Version:'):
                    fields = line.split()
                    if len(fields) == 2:
                        foundVersion = True
                        line = (fields[0] + '       ' + 
                                str(version[0]).rjust(2,'0') + '.' +
                                str(version[1]) + '.' + 
                                str(version[2]) + '.' +
                                str(version[3]) + '\n')

                # Update tarball version.
                elif not foundSource and line.startswith('Source0:'):
                    fields = line.split()
                    if len(fields) == 2:
                        foundSource = True
                        line = (fields[0] + '       ' + version_prefix +
                                str(version[0]).rjust(2,'0') + '.' + 
                                str(version[1]) + '.' + 
                                str(version[2]) + '.' +
                                str(version[3]) + '.tar.gz\n')

                ostream.write(line)
        ostream.close()


    def _generate_script_version(self, vendor, script_file, version):
        """
        Update Script files with version
        """
        with open(script_file, 'r') as istream:
            data = istream.readlines()
        istream.close()
        #print (data)

        version_str = ( '"' + str(version[0]).rjust(2,'0') + '.' +
                        str(version[1]) + '.' +
                        str(version[2]) + '.' +
                        str(version[3]) + '"' )

        foundVersion = False
        with open(script_file, 'w') as ostream:
            for line in data:
                if not foundVersion and line.startswith('ADAPTER_VERSION'):
                    line = "ADAPTER_VERSION=" + version_str + '\n'
                    foundVersion = True

                ostream.write(line)
        ostream.close()


    def _generate_galaxy_version(self, vendor, galaxy_file, version):
        """
        Update Script files with version
        """
        with open(galaxy_file, 'r') as istream:
            data = istream.readlines()
        istream.close()
        #print (data)

        version_str = ( str(version[0]).rjust(2,'0') + '.' +
                        str(version[1]) + '.' +
                        str(version[2]) + '.' +
                        str(version[3]) )

        foundVersion = False
        with open(galaxy_file, 'w') as ostream:
            for line in data:
                if not foundVersion and line.startswith('version:'):
                    line = "version: " + version_str + '\n'
                    foundVersion = True

                ostream.write(line)
        ostream.close()


    def write_version(self, newversion):
        """
        Update versioning files.
        """
        print ('Generating new version files.')
        self._generate_build_version(self.vendorType.Hitachi, self.build_file, newversion)
        self._generate_build_version(self.vendorType.HPE, self.build_hpe_file, newversion)

        # Update version information in RPM spec files.
        self._generate_spec_version(self.vendorType.Hitachi, self.rpm_file, newversion)
        self._generate_spec_version(self.vendorType.HPE, self.rpm_hpe_file, newversion)

        # Update version information in Scripts files.
        self._generate_script_version(self.vendorType.Hitachi, self.script_file, newversion)
        self._generate_script_version(self.vendorType.HPE, self.script_hpe_file, newversion)

        # Update version information in ansible galaxy files.
        self._generate_galaxy_version(self.vendorType.Hitachi, self.galaxy_file, newversion)
        self._generate_galaxy_version(self.vendorType.HPE, self.galaxy_hpe_file, newversion)

        # Save new version
        self._generate_sh_version(self.sh_file, newversion)


    def next_major_version(self, version):
        """
        Update version to next major version.
        """
        version[0] += 1
        version[1] = 0
        version[2] = 0
        return version

    def next_minor_version(self, version):
        """
        Update version to next minor version.
        """
        version[1] += 1
        version[2] = 0
        return version

    def next_patch_version(self, version):
        """
        Update version to next patch version.
        """
        version[2] += 1
        return version

    def git_add(self):
        """
        Add modified versioning files to facilitate committing.
        Includes rpm spec files and docker yaml files.
        """
        gitcmd = ['/usr/bin/git', 'add',
                  self.sh_file,
                  self.build_file,
                  self.build_hpe_file,
                  self.rpm_file,
                  self.rpm_hpe_file,
                  self.script_file,
                  self.script_hpe_file,
                  ]
        subprocess.check_output(gitcmd, stderr=subprocess.STDOUT)


def Main(argv):
    """
    Parse CLI to determine how to update build version number.
    If no arguments, just display the current build version.
    """
    optionHelp = 0
    optionVerbose = 0
    optionVersion = 0

    optionMajor = 0
    optionMinor = 0
    optionPatch = 0
    optionBuild = 0
    optionManual = 0
    optionBuildNumber = 0

    #
    # Scan for existing version files (e.g. version.inc and version.h
    # and collect the existing version.
    #
    versionObj =  build_versioning()
    version = versionObj.current()
    versionLen = len(version) -1

    #
    # Parse CLI to determine desired operation.
    #
    for arg in sys.argv[1:]:
        if arg == '-h':
            optionHelp = 1
        elif arg == '-v':
            optionVerbose = 1
        elif arg == '--help':
            optionHelp = 1
        elif arg == '--verbose':
            optionVerbose = 1
        elif arg == '--version':
            optionVersion = 1
        elif arg == '--major':
            # Last choice wins.
            optionMajor  = 1
            optionMinor  = 0
            optionPatch  = 0
        elif arg == '--minor':
            # Last choice wins.
            optionMajor  = 0
            optionMinor  = 1
            optionPatch  = 0
        elif arg == '--patch':
            # Last choice wins.
            optionMajor  = 0
            optionMinor  = 0
            optionPatch  = 1
        else:
            fields = arg.split('.')
            if len(fields) == 0:
                print('*** ERROR: Invalid option:', arg, '\n')
                sys.exit(errno.EINVAL)
            if len(fields) == 1:
                try:
                    version[3] = int( fields[0] )
                    optionBuildNumber = 1
                except:
                    print ('*** ERROR: Invalid build number:', arg, '\n')
                    sys.exit(errno.EINVAL)
            elif len(fields) != versionLen:
                print(len(fields))
                print('*** ERROR: Invalid version number:', arg, '\n')
                sys.exit(errno.EINVAL)
            else:
                try:
                    for i in range(0, versionLen):
                        version[i] = int( fields[i] )
                    version[3] = 7
                    optionManual = 1
                except:
                    print ('*** ERROR: Invalid version number:', arg, '\n')
                    sys.exit(errno.EINVAL)

    if optionVersion:
        print ('%s %s' % (utilName, utilVersion))
        sys.exit(0)

    if optionHelp:
        print ('Autogenerate Usage:', 'new_version.py --minor')
        print ('Manual Usage:', 'new_version.py 8.5.1')
        print ('\nArguments:')
        print ('\tmm.nn.pp   - Manually set version to mm.nn.pp.')
        print ('\t--major    - Autogenerate next major version.')
        print ('\t--minor    - Autogenerate next minor version.')
        print ('\t--patch    - Autogenerate next patch version.')
        print ()
        print ('\t--help     - Display help')
        print ()
        sys.exit(0)

    #
    # Automatically update version.
    #
    if optionMajor:
        version = versionObj.next_major_version(version)
        #print('Major Version:', version)
        versionObj.write_version(version)
        versionObj.git_add()
    elif optionMinor:
        version = versionObj.next_minor_version(version)
        #print('Minor Version:', version)
        versionObj.write_version(version)
        versionObj.git_add()
    elif optionPatch:
        version = versionObj.next_patch_version(version)
        #print('Patch Version:', version)
        versionObj.write_version(version)
        versionObj.git_add()
    elif optionBuildNumber:
        versionObj.write_version(version)
    elif optionManual:
        versionObj.write_version(version)
        versionObj.git_add()


    # Pretty print the version.
    #verStr = '0' + str(version[0]) + '.' + str(version[1]) + '.' + str(version[2]) + '.00' + str(version[3])
    verStr = '0' + str(version[0]) + '.' + str(version[1]) + '.' + str(version[2])
    print('Current version:', verStr)
    sys.exit(0)


if __name__ == "__main__":
  Main(sys.argv[1:])
