from __future__ import print_function
from __future__ import absolute_import

__license__ = """

Copyright (c) 2012-2014, Uwe Schmitt, all rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

Neither the name of the ETH Zurich nor the names of its contributors may be
used to endorse or promote products derived from this software without specific
prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import os.path
import re
from collections import defaultdict
from autowrap.ConversionProvider import setup_converter_registry
from autowrap.DeclResolver import (ResolvedClass, ResolvedEnum, ResolvedTypeDef, ResolvedFunction)
from autowrap.code_generators.CodeGeneratorBase import CodeGeneratorBase
import autowrap.Code as Code
import logging as logger
from autowrap.code_generators.Utils import augment_arg_names
from cppcli import *

IS_PY3 = True
try:
	unicode = unicode
except NameError:
	# 'unicode' is undefined, must be Python 3
	str = str
	unicode = str
	bytes = bytes
	basestring = (str, bytes)
else:
	IS_PY3 = False
	# 'unicode' exists, must be Python 2
	str = str
	unicode = unicode
	bytes = str
	basestring = basestring

class CLRGenerator(CodeGeneratorBase):
	def __init__(self, resolved, instance_mapping, pyx_target_path=None, manual_code=None, extra_cimports=None,
				 allDecl={}):
		if IS_PY3:
			super().__init__(resolved, instance_mapping, pyx_target_path, manual_code,
							 extra_cimports, allDecl)
		else:
			super(CodeGeneratorBase, self).__init__(resolved, instance_mapping, pyx_target_path, manual_code,
													extra_cimports, allDecl)

	def create_code_file(self, debug=False):
		pass


	def create_wrapper_for_class(self, decl):
		# wrap any enum code
		self.class_codes[decl.name] = self.create_wrapper_for_enum(decl)
		# handle wrap-as+attach annotations
		for class_name in decl.cpp_decl.annotations.get("wrap-attach", []):
			code = Code.Code()
			display_name = decl.cpp_decl.annotations.get("wrap-as", [decl.name])[0]
			code.add("%s = %s" % (display_name, "__" + decl.name))
			self.class_codes[class_name].add(code)

	def create_method_wrapper(self):
		"""Create a wrapper for calling method"""
		pass

	def create_property_wrapper(self):
		"""Create a get/set property for field with get/set methods"""
		pass
	
	def create_wrapper_for_enum(self, decl):
		return EnumWrapper(decl).render_header()

