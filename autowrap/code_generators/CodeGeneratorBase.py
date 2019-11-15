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
from autowrap.Types import CppType
from autowrap.code_generators.Utils import fixed_include_dirs


class CodeGeneratorBase(object):
	"""
    This is the main Code Generator.

    Its main entry function is "create_pyx_file" which generates the pyx file
    from the input (given in the initializiation).

    The actual conversion of input/output arguments is done in the
	ConversionProviders for each argument type.
	"""

	def __init__(self, resolved, instance_mapping, pyx_target_path=None,
				 manual_code=None, extra_cimports=None, allDecl={}):
		if manual_code is None:
			manual_code = dict()

		self.manual_code = manual_code
		self.extra_cimports = extra_cimports

		self.include_shared_ptr = True
		self.include_refholder = True
		self.include_numpy = False

		self.target_path = os.path.abspath(pyx_target_path)
		self.target_pxd_path = self.target_path.split(".pyx")[0] + ".pxd"
		self.target_dir = os.path.dirname(self.target_path)

		# If true, we will write separate pxd and pyx files (need to ensure the
		# right code goes to header if we use pxd headers). Alternatively, we
		# will simply write a single pyx file.
		self.write_pxd = len(allDecl) > 0

		## Step 1: get all classes of current module
		self.classes = [d for d in resolved if isinstance(d, ResolvedClass)]
		self.enums = [d for d in resolved if isinstance(d, ResolvedEnum)]
		self.functions = [d for d in resolved if isinstance(d, ResolvedFunction)]
		self.typedefs = [d for d in resolved if isinstance(d, ResolvedTypeDef)]

		self.resolved = []
		self.resolved.extend(sorted(self.typedefs, key=lambda d: d.name))
		self.resolved.extend(sorted(self.enums, key=lambda d: d.name))
		self.resolved.extend(sorted(self.functions, key=lambda d: d.name))
		self.resolved.extend(sorted(self.classes, key=lambda d: d.name))

		self.instance_mapping = instance_mapping
		self.allDecl = allDecl

		## Step 2: get classes of complete project (includes other modules)
		self.all_typedefs = self.typedefs
		self.all_enums = self.enums
		self.all_functions = self.functions
		self.all_classes = self.classes
		self.all_resolved = self.resolved
		if len(allDecl) > 0:

			self.all_typedefs = []
			self.all_enums = []
			self.all_functions = []
			self.all_classes = []
			for modname, v in allDecl.items():
				self.all_classes.extend([d for d in v["decls"] if isinstance(d, ResolvedClass)])
				self.all_enums.extend([d for d in v["decls"] if isinstance(d, ResolvedEnum)])
				self.all_functions.extend([d for d in v["decls"] if isinstance(d, ResolvedFunction)])
				self.all_typedefs.extend([d for d in v["decls"] if isinstance(d, ResolvedTypeDef)])

			self.all_resolved = []
			self.all_resolved.extend(sorted(self.all_typedefs, key=lambda d: d.name))
			self.all_resolved.extend(sorted(self.all_enums, key=lambda d: d.name))
			self.all_resolved.extend(sorted(self.all_functions, key=lambda d: d.name))
			self.all_resolved.extend(sorted(self.all_classes, key=lambda d: d.name))

		# Register using all classes so that we know about the complete project
		self.cr = setup_converter_registry(self.all_classes, self.all_enums, instance_mapping)
		self.top_level_code = []
		self.top_level_pyx_code = []
		self.class_codes = defaultdict(list)
		self.class_codes_extra = defaultdict(list)
		self.class_pxd_codes = defaultdict(list)
		self.wrapped_enums_cnt = 0
		self.wrapped_classes_cnt = 0
		self.wrapped_methods_cnt = 0

	def get_include_dirs(self, include_boost):
		if self.pxd_dir is not None:
			return fixed_include_dirs(include_boost) + [self.pxd_dir]
		else:
			return fixed_include_dirs(include_boost)

	def setup_cimport_paths(self):
		pxd_dirs = set()
		for inst in self.all_classes + self.all_enums + self.all_functions + self.all_typedefs:
			pxd_path = os.path.abspath(inst.cpp_decl.pxd_path)
			pxd_dir = os.path.dirname(pxd_path)
			pxd_dirs.add(pxd_dir)
			pxd_file = os.path.basename(pxd_path)
			inst.pxd_import_path, __ = os.path.splitext(pxd_file)
		assert len(pxd_dirs) <= 1, "pxd files must be located in same directory"
		self.pxd_dir = pxd_dirs.pop() if pxd_dirs else None

	def filterout_iterators(self, methods):
		"""
		Splits methods into iterators, and non_iterators
		:param methods: The resolved methods to parse for iterator annotations 
		:return: (iterators, non_iterator_methods)
		"""

		def parse(anno):
			m = re.match(r"(\S+)\((\S+)\)", anno)
			assert m is not None, "invalid iter annotation"
			name, type_str = m.groups()
			return name, CppType.from_string(type_str)

		begin_iterators = dict()
		end_iterators = dict()
		non_iter_methods = defaultdict(list)
		for name, mi in methods.items():
			for method in mi:
				annotations = method.cpp_decl.annotations
				if "wrap-iter-begin" in annotations:
					py_name, res_type = parse(annotations["wrap-iter-begin"])
					begin_iterators[py_name] = (method, res_type)
				elif "wrap-iter-end" in annotations:
					py_name, res_type = parse(annotations["wrap-iter-end"])
					end_iterators[py_name] = (method, res_type)
				else:
					non_iter_methods[name].append(method)

		begin_names = set(begin_iterators.keys())
		end_names = set(end_iterators.keys())
		common_names = begin_names & end_names
		if begin_names != end_names:
			# TODO: diesen fall testen
			raise Exception("iter declarations not balanced")

		for py_name in common_names:
			__, res_type_begin = begin_iterators[py_name]
			__, res_type_end = end_iterators[py_name]
			assert res_type_begin == res_type_end, "iter value types do not match"

		begin_methods = dict((n, m) for n, (m, __) in begin_iterators.items())
		end_methods = dict((n, m) for n, (m, __) in end_iterators.items())
		res_types = dict((n, t) for n, (__, t) in end_iterators.items())

		iterators = dict()
		for n in common_names:
			iterators[n] = (begin_methods[n], end_methods[n], res_types[n])

		return iterators, non_iter_methods

	# --- ABSTRACT METHODS ---
	def create_code_file(self, debug=False):
		raise NotImplementedError

	def create_wrapper_for_enum(self, decl):
		raise NotImplementedError

	def create_wrapper_for_class(self, r_class):
		raise NotImplementedError

	def _create_iter_methods(self, iterators, instance_mapping, local_mapping):
		raise NotImplementedError

	def _create_overloaded_method_decl(self, py_name, dispatched_m_names, methods, use_return, use_kwargs=False):
		raise NotImplementedError

	def create_wrapper_for_method(self, cdcl, py_name, methods):
		raise NotImplementedError

	def _create_fun_decl_and_input_conversion(self, code, py_name, method, is_free_fun=False):
		raise NotImplementedError

	def _create_wrapper_for_attribute(self, attribute):
		raise NotImplementedError

	def create_wrapper_for_nonoverloaded_method(self, cdcl, py_name, method):
		raise NotImplementedError

	def create_wrapper_for_free_function(self, decl):
		raise NotImplementedError

	def _create_wrapper_for_free_function(self, decl, name=None, orig_cpp_name=None):
		raise NotImplementedError

	def create_wrapper_for_constructor(self, class_decl, constructors):
		raise NotImplementedError

	def create_wrapper_for_nonoverloaded_constructor(self, class_decl, py_name, cons_decl):
		raise NotImplementedError

	def create_special_mul_method(self, cdcl, mdcl):
		raise NotImplementedError

	def create_special_add_method(self, cdcl, mdcl):
		raise NotImplementedError

	def create_special_iadd_method(self, cdcl, mdcl):
		raise NotImplementedError

	def create_special_getitem_method(self, mdcl):
		raise NotImplementedError

	def create_cast_methods(self, mdecls):
		raise NotImplementedError

	def create_special_cmp_method(self, cdcl, ops):
		raise NotImplementedError

	def create_special_copy_method(self, class_decl):
		raise NotImplementedError

	def create_foreign_cimports(self):
		raise NotImplementedError

	def create_cimports(self):
		raise NotImplementedError

	def create_default_cimports(self):
		raise NotImplementedError

	def create_std_cimports(self):
		raise NotImplementedError

	def create_includes(self):
		raise NotImplementedError
